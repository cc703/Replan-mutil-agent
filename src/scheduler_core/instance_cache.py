"""Versioned instance cache with strict integrity and optional regeneration."""

import base64
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

from scheduler_core.generate import generate_instance
from scheduler_core.generation.canonical import instance_from_bytes, instance_to_bytes
from scheduler_core.generation.integrity import check_generated_profile
from scheduler_core.generation.params import GeneratorParams, validate_inputs
from scheduler_core.models import Instance
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.io.errors import ArtifactError, UnsafePathError


class CacheConflictError(ArtifactError):
    """Cached data disagrees with its key, metadata, or regeneration."""


class CacheMeta(BaseModel):
    """Strict persisted metadata: versions, request, hashes, size and NumPy version.

    ``schema_version`` serializes as ``schema``; parameter and instance hashes
    are SHA-256 hex digests. The NumPy version is informational. Hashes detect
    accidental corruption but do not authenticate a cache entry.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal[1] = Field(alias="schema")
    canonical_version: Literal[1]
    generator_version: Literal["c2-1"]
    scale: Literal["S", "M", "L"]
    utilization: float
    deadline_tightness: float
    seed: int = Field(ge=0, le=2**63 - 1)
    params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    instance_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    instance_bytes: int = Field(ge=0)
    numpy_version: str = Field(min_length=1)

    @field_validator("schema_version", "canonical_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("version must be an integer")
        return value


@dataclass(frozen=True)
class CacheResult:
    """Instance and its cache key/path, reuse flag and regeneration-check flag.

    The instance contains integer time slots of five minutes by default. A true
    ``regeneration_verified`` means bytes matched a fresh generation; it is not
    a cryptographic proof of origin.
    """

    instance: Instance
    key: str
    directory: Path
    reused: bool
    regeneration_verified: bool


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _float_token(value: float) -> str:
    return struct.pack(">d", 0.0 if value == 0 else value).hex()


def _params_hash(params: GeneratorParams) -> str:
    values = params.model_dump(mode="json")
    for key, value in values.items():
        if isinstance(value, float) and value == 0:
            values[key] = 0.0
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class InstanceCache:
    """Cache generated instances using only ArtifactStore's cache area."""

    def __init__(self, store: ArtifactStore) -> None:
        self.area = store.cache("instances")

    def get_or_generate(
        self,
        scale: str,
        utilization: float,
        deadline_tightness: float,
        seed: int,
        *,
        params: GeneratorParams | None = None,
        verify_regeneration: bool = False,
    ) -> CacheResult:
        """Return a validated cached instance, generating and publishing if absent.

        Scale is S, M or L; utilization is in [0.05, 1], deadline tightness in
        [0, 1], and seed is an integer in [0, 2**63-1]. Numeric factors reject
        bool and non-finite values. Params are optional validated generation
        parameters; the verification flag must be bool. Inputs are not modified.
        Instance times use the axis's integer slots (five minutes by default).

        A miss creates an immutable cache entry through the store; a hit reads
        it without overwriting. Verification regenerates and compares bytes,
        including on a newly created entry. Hashes alone do not authenticate data.
        Invalid inputs raise TypeError or ValueError before cache access;
        inconsistent data raises CacheConflictError, unsafe paths UnsafePathError,
        and filesystem or unsupported-publication failures may raise OSError.
        """
        if not isinstance(verify_regeneration, bool):
            raise TypeError("verify_regeneration must be a bool")
        scale, u, t, seed, p = validate_inputs(scale, utilization, deadline_tightness, seed, params)
        digest = _params_hash(p)
        key = f"{dict(S='small', M='medium', L='large')[scale]}_u{_float_token(u)}_t{_float_token(t)}_s{seed}"
        if p != GeneratorParams():
            key += (
                "_p" + base64.b32encode(bytes.fromhex(digest)).decode("ascii").rstrip("=").lower()
            )
        files = self._get(key)
        reused = files is not None
        if files is None:
            instance = generate_instance(scale, u, t, seed, params=p)
            data = instance_to_bytes(instance)
            meta = CacheMeta(
                schema=1,
                canonical_version=1,
                generator_version="c2-1",
                scale=cast(Literal["S", "M", "L"], scale),
                utilization=u,
                deadline_tightness=t,
                seed=seed,
                params_sha256=digest,
                instance_sha256=hashlib.sha256(data).hexdigest(),
                instance_bytes=len(data),
                numpy_version=np.__version__,
            )
            files = {
                "instance.json": data,
                "meta.json": (meta.model_dump_json(by_alias=True) + "\n").encode(),
            }
            try:
                self.area.put(key, files)
            except FileExistsError:
                files = self._get(key)
                if files is None:
                    raise CacheConflictError("concurrent entry disappeared")
                reused = True
        return self._read(key, files, scale, u, t, seed, p, digest, reused, verify_regeneration)

    def _get(self, key: str) -> dict[str, bytes] | None:
        try:
            return self.area.get(key)
        except UnsafePathError:
            raise
        except ArtifactError as exc:
            raise CacheConflictError(str(exc)) from exc

    def _read(
        self,
        key: str,
        files: dict[str, bytes],
        scale: str,
        u: float,
        t: float,
        seed: int,
        params: GeneratorParams,
        digest: str,
        reused: bool,
        verify: bool,
    ) -> CacheResult:
        try:
            if set(files) != {"meta.json", "instance.json"}:
                raise ValueError("unexpected cache files")
            raw = json.loads(
                files["meta.json"],
                object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
            )
            meta = CacheMeta.model_validate(raw)
            data = files["instance.json"]
            if (
                meta.scale,
                meta.utilization,
                meta.deadline_tightness,
                meta.seed,
                meta.params_sha256,
                meta.instance_sha256,
                meta.instance_bytes,
            ) != (scale, u, t, seed, digest, hashlib.sha256(data).hexdigest(), len(data)):
                raise ValueError("metadata mismatch")
            instance = instance_from_bytes(data)
            check_generated_profile(instance, scale)
            if (
                verify
                and instance_to_bytes(generate_instance(scale, u, t, seed, params=params)) != data
            ):
                raise ValueError("regeneration mismatch; NumPy versions may differ")
        except (ValueError, TypeError, KeyError) as exc:
            raise CacheConflictError(str(exc)) from exc
        return CacheResult(instance, key, self.area.parent / key, reused, verify)
