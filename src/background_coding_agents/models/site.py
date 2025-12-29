"""
Site configuration models for manufacturing plants.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PLCType(str, Enum):
    """Supported PLC types."""

    SIEMENS_S7_1500 = "Siemens S7-1500"
    SIEMENS_S7_1200 = "Siemens S7-1200"
    SIEMENS_S7_300 = "Siemens S7-300"
    ALLEN_BRADLEY_CONTROLLOGIX = "Allen-Bradley ControlLogix"
    ALLEN_BRADLEY_COMPACTLOGIX = "Allen-Bradley CompactLogix"
    BECKHOFF_TWINCAT = "Beckhoff TwinCAT"
    CODESYS = "CODESYS"
    SCHNEIDER_M340 = "Schneider M340"
    SCHNEIDER_M580 = "Schneider M580"
    MITSUBISHI_MELSEC = "Mitsubishi MELSEC"
    OMRON_NX = "Omron NX"
    OTHER = "Other"


class SafetyRating(str, Enum):
    """IEC 61508 Safety Integrity Levels."""

    NONE = "None"
    SIL_1 = "SIL-1"
    SIL_2 = "SIL-2"
    SIL_3 = "SIL-3"
    SIL_4 = "SIL-4"

    @property
    def level(self) -> int:
        """Get numeric safety level (0-4)."""
        mapping = {"None": 0, "SIL-1": 1, "SIL-2": 2, "SIL-3": 3, "SIL-4": 4}
        return mapping.get(self.value, 0)

    def __ge__(self, other: "SafetyRating") -> bool:
        return self.level >= other.level

    def __gt__(self, other: "SafetyRating") -> bool:
        return self.level > other.level


class SiteConfig(BaseModel):
    """
    Manufacturing site configuration.

    Represents a single plant/facility with its PLC systems,
    safety requirements, and repository information.
    """

    name: str = Field(..., description="Unique site identifier", min_length=1)
    location: str = Field(..., description="Physical location (city, country)")
    plc_type: PLCType = Field(..., description="Primary PLC platform")
    firmware_version: str = Field(
        ..., description="PLC firmware version (e.g., '2.9.3')"
    )
    line_type: str = Field(
        default="General", description="Production line type (Assembly, Welding, etc.)"
    )
    repo_path: str = Field(..., description="Path to site's code repository")
    safety_rating: SafetyRating = Field(
        default=SafetyRating.NONE, description="IEC 61508 Safety Integrity Level"
    )

    # Optional extended configuration
    description: str | None = Field(default=None, description="Site description")
    timezone: str = Field(default="UTC", description="Site timezone")
    owner_email: str | None = Field(default=None, description="Site owner contact")
    tags: list[str] = Field(default_factory=list, description="Site tags for filtering")

    # Technical details
    ip_address: str | None = Field(default=None, description="PLC IP address")
    protocol: str = Field(
        default="OPC UA", description="Communication protocol (OPC UA, Modbus, etc.)"
    )
    max_cycle_time_ms: int = Field(
        default=100, description="Maximum PLC cycle time in milliseconds", ge=1
    )

    # Safety constraints
    requires_safety_review: bool = Field(
        default=True, description="Whether changes require safety review"
    )
    certified_modules: list[str] = Field(
        default_factory=list,
        description="List of certified safety modules that cannot be modified",
    )
    restricted_io: list[str] = Field(
        default_factory=list, description="I/O points that require special approval"
    )

    # Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional site-specific metadata"
    )

    @field_validator("firmware_version")
    @classmethod
    def validate_firmware_version(cls, v: str) -> str:
        """Validate firmware version format."""
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError(
                "Firmware version must have at least major.minor format (e.g., '2.9')"
            )
        return v

    @property
    def is_safety_critical(self) -> bool:
        """Check if site has safety-critical rating (SIL-2 or higher)."""
        return self.safety_rating >= SafetyRating.SIL_2

    @property
    def firmware_major_version(self) -> int:
        """Get major firmware version number."""
        return int(self.firmware_version.split(".")[0])

    def matches_filter(self, filter_config: dict[str, Any]) -> bool:
        """Check if site matches a filter configuration."""
        if "plc_type" in filter_config:
            if self.plc_type.value != filter_config["plc_type"]:
                return False

        if "firmware_version" in filter_config:
            if not self.firmware_version.startswith(filter_config["firmware_version"]):
                return False

        if "safety_rating" in filter_config:
            required = SafetyRating(filter_config["safety_rating"])
            if self.safety_rating < required:
                return False

        if "location" in filter_config:
            if filter_config["location"].lower() not in self.location.lower():
                return False

        if "tags" in filter_config:
            required_tags = set(filter_config["tags"])
            if not required_tags.issubset(set(self.tags)):
                return False

        return True

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Plant-01-Assembly",
                    "location": "Detroit, MI",
                    "plc_type": "Siemens S7-1500",
                    "firmware_version": "2.9.3",
                    "line_type": "Assembly",
                    "repo_path": "/repos/plant-01-assembly",
                    "safety_rating": "SIL-2",
                }
            ]
        }
    }
