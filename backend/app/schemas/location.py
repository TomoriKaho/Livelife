"""WGS-84 device payload compatible with PR #82's CurrentLocation interface."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from app.schemas.information import (
    InformationQuery,
    Latitude,
    LocationResolution,
    Longitude,
    MapPlace,
)


class DeviceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: Latitude
    longitude: Longitude
    accuracy: Annotated[FiniteFloat, Field(ge=0)]
    timestamp: Annotated[FiniteFloat, Field(ge=0)]
    heading: Annotated[FiniteFloat, Field(ge=0, lt=360)] | None = None


class NearbyEventsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: DeviceLocation
    radius_m: Annotated[FiniteFloat, Field(gt=0, le=50_000)]
    filters: InformationQuery = Field(default_factory=InformationQuery)

    def query(self) -> InformationQuery:
        if any(
            v is not None
            for v in (self.filters.longitude, self.filters.latitude, self.filters.radius_m)
        ):
            raise ValueError("supply the query center through location and radius_m only")
        return self.filters.model_copy(
            update={
                "longitude": self.location.longitude,
                "latitude": self.location.latitude,
                "radius_m": self.radius_m,
                "events_only": True,
            }
        )


class ResolvedPlace(BaseModel):
    resolution: LocationResolution
    place: MapPlace | None
