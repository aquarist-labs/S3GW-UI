# Copyright 2023 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from datetime import datetime as dt
from typing import List, Literal, Optional

from pydantic import BaseModel
from pydantic.fields import Field
from types_aiobotocore_s3.literals import (
    ObjectLockLegalHoldStatusType,
    ObjectLockModeType,
    ObjectLockRetentionModeType,
)
from types_aiobotocore_s3.type_defs import OwnerTypeDef


class AuthUser(BaseModel):
    ID: str
    DisplayName: str
    IsAdmin: bool


class Bucket(BaseModel):
    Name: str
    CreationDate: Optional[dt] = None

    def __eq__(self, other: Bucket) -> bool:
        return (
            self.Name == other.Name and self.CreationDate == other.CreationDate
            if (
                self.CreationDate is not None and other.CreationDate is not None
            )
            else self.Name == other.Name
        )


class Tag(BaseModel):
    Key: str
    Value: str

    def __eq__(self, other: Tag) -> bool:
        return self.Key == other.Key and self.Value == other.Value

    def __hash__(self):  # pyright: ignore [reportIncompatibleVariableOverride]
        return hash((self.Key, self.Value))


class TagSet(BaseModel):
    TagSet: List[Tag]


class BucketObjectLock(BaseModel):
    ObjectLockEnabled: Optional[bool]
    RetentionEnabled: Optional[bool]
    RetentionMode: Optional[ObjectLockRetentionModeType] = None
    RetentionValidity: Optional[int]
    RetentionUnit: Optional[Literal["Days", "Years"]]

    def __eq__(self, other: BucketObjectLock) -> bool:
        return (
            self.ObjectLockEnabled == other.ObjectLockEnabled
            and self.RetentionEnabled == other.RetentionEnabled
            and self.RetentionMode == other.RetentionMode
            and self.RetentionValidity == other.RetentionValidity
            and self.RetentionUnit == other.RetentionUnit
        )


class BucketAttributes(Bucket, BucketObjectLock, TagSet):
    VersioningEnabled: Optional[bool]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BucketAttributes):
            return (
                self.VersioningEnabled == other.VersioningEnabled
                and Bucket.__eq__(self, other)
                and BucketObjectLock.__eq__(self, other)
                and set(self.TagSet) == set(other.TagSet)
            )
        if isinstance(other, BucketObjectLock):
            return BucketObjectLock.__eq__(self, other)
        if isinstance(other, Bucket):
            return Bucket.__eq__(self, other)
        else:
            return NotImplemented


class Object(BaseModel):
    Key: str
    VersionId: Optional[str] = None
    LastModified: Optional[dt] = None
    ETag: Optional[str] = None
    ObjectLockMode: Optional[ObjectLockModeType] = None
    ObjectLockRetainUntilDate: Optional[dt] = None
    ObjectLockLegalHoldStatus: Optional[ObjectLockLegalHoldStatusType] = None
    Owner: Optional[OwnerTypeDef] = None
    ContentType: Optional[str] = None
    Name: str
    Size: Optional[int] = None
    Type: Literal["OBJECT", "FOLDER"] = "OBJECT"


class DeletedObject(BaseModel):
    Key: str
    VersionId: Optional[str] = None
    DeleteMarker: Optional[bool] = None
    DeleteMarkerVersionId: Optional[str] = None


class ObjectIdentifier(BaseModel):
    Key: str
    VersionId: str = ""


class ObjectRequest(ObjectIdentifier):
    pass


class ListObjectsRequest(BaseModel):
    Prefix: str = ""
    Delimiter: str = "/"


class ListObjectVersionsRequest(ListObjectsRequest):
    Strict: bool = Field(
        default=False,
        description="If `True`, then only the objects whose key "
        "exactly match the specified prefix are returned.",
    )


class ObjectVersion(Object):
    IsDeleted: bool
    IsLatest: bool


class ObjectLockLegalHold(BaseModel):
    Status: ObjectLockLegalHoldStatusType


class ObjectAttributes(Object, TagSet):
    pass


class SetObjectTaggingRequest(ObjectIdentifier, TagSet):
    pass


class SetObjectLockLegalHoldRequest(ObjectIdentifier):
    LegalHold: ObjectLockLegalHold


class RestoreObjectRequest(ObjectIdentifier):
    pass


class DeleteObjectRequest(ObjectIdentifier):
    AllVersions: bool = Field(
        default=False,
        description="If `True`, all versions will be deleted, otherwise "
        "only the specified one.",
    )


class DeleteObjectByPrefixRequest(BaseModel):
    Prefix: str = Field(
        title="The prefix of the objects to delete.",
        description="Note, a prefix like `a/b/` will delete all objects "
        "starting with that prefix, whereas `a/b` will only delete this "
        "specific object.",
    )
    Delimiter: str = "/"
    AllVersions: bool = Field(
        default=False,
        description="If `True`, all versions will be deleted, otherwise "
        "the latest one.",
    )
