from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Field, Relationship, SQLModel


class DataObject(BaseModel):
    class Config:
        # Allow extra fields in the data object and treat them as attributes
        extra = "allow"


class SipAccountData(SQLModel, table=True):
    __tablename__ = 'sip_accounts_data'
    __database__ = 'sipthor_db'
    id: int = Field(default=None, primary_key=True)
    account_id: int = Field(default=None, foreign_key="sip_accounts_meta.id")
    profile: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    account: "SipAccount" = Relationship(back_populates="data",
                                         sa_relationship_kwargs={"lazy": "joined"},
                                         )


class SipAccount(SQLModel, table=True):
    __tablename__ = 'sip_accounts_meta'
    __database__ = 'sipthor_db'
    id: int = Field(default=None, primary_key=True)
    username: str = Field(max_length=64)
    domain: str = Field(max_length=64)
    first_name: Optional[str] = Field(default=None, max_length=64)
    last_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=64)
    customer_id: int = Field(default=0)
    reseller_id: int = Field(default=0)
    owner_id: int = Field(default=0)
    change_date: Optional[str] = Field(default=None)

    # Relationships
    data: List[SipAccountData] = Relationship(back_populates="account",
                                              sa_relationship_kwargs={"lazy": "joined"},
                                              # cascade='all, delete-orphan'
                                              )

    def set_profile(self, value: dict):
        if not self.data:
            SipAccountData(account=self, profile=value)
        else:
            flag_modified(self.data[0], "profile")
            self.data[0].profile = value

    @property
    def profile(self) -> Optional[dict]:
        return self.data[0].profile if self.data else None

    @profile.setter
    def profile(self, value: dict):
        self.set_profile(value)
