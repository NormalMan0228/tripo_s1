from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Credentials(Strict):
    username: str = Field(min_length=3,max_length=24,pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(min_length=10,max_length=128)
    invitation: str = Field(default='',max_length=256)

class Mutation(Strict):
    request_id: UUID


def strong_password(value: str) -> bool:
    """New passwords need an uppercase letter and a special character (length is
    checked by Credentials)."""
    return any(c.isupper() for c in value) and any(not c.isalnum() for c in value)


class AdminGrant(Mutation):
    shards: int = Field(default=0, ge=0, le=100000)
    coins: int = Field(default=0, ge=0, le=100000)

class RunStart(Mutation):
    map_id: Literal['forest','quarry','frost'] = 'forest'
    difficulty: Literal['relaxed','standard','veteran'] = 'standard'
    chapter_id: Literal['','first_fire','quiet_quarry','returning_light'] = ''

class Avatar(Strict):
    character: Literal['explorer_b','explorer','ranger','tinker'] = 'explorer_b'
    hair: str = Field(default='#30595b',pattern=r'^#[0-9a-fA-F]{6}$')
    coat: str = Field(default='#dba448',pattern=r'^#[0-9a-fA-F]{6}$')
    pants: str = Field(default='#526552',pattern=r'^#[0-9a-fA-F]{6}$')
    boots: str = Field(default='#765744',pattern=r'^#[0-9a-fA-F]{6}$')
    skin: Literal['#e4b587','#f0cdb1','#bc865c','#895b43','#604431'] = '#e4b587'
    headwear: Literal['none','cap','beret'] = 'none'
    backpack: bool = True

class AvatarEdit(Mutation):
    version: int = Field(ge=0)
    avatar: Avatar

class LifeAction(Mutation):
    version: int = Field(ge=0)
    action: Literal['plant','water','harvest','cast','reel','cancel_fishing','gather','buy','sell','order']
    plot: int = Field(default=0,ge=0,le=5)
    item: str = Field(default='',max_length=24)
    spot: Literal['pond','sea'] = 'pond'
    quantity: int = Field(default=1,ge=1,le=20)

class ObjectEdit(Mutation):
    version: int = Field(ge=1)
    action: Literal['paint','place','retrieve']
    color: str = Field(default='#f6eee0',pattern=r'^#[0-9a-fA-F]{6}$')
    x: float = Field(default=0,ge=-130,le=130)
    z: float = Field(default=0,ge=-130,le=130)
    rotation: Literal[0,90,180,270] = 0

class Input(Strict):
    sequence: int = Field(ge=1,le=2147483647)
    dx: float = Field(default=0,ge=-1,le=1)
    dz: float = Field(default=0,ge=-1,le=1)
    sprint: bool = False
    action: Literal['','harvest','eat','heal','craft','fire','attack'] = ''
    target: str = Field(default='',max_length=32)

class Generate(Mutation):
    prompt: str = Field(min_length=3,max_length=500)

    @field_validator('prompt')
    @classmethod
    def meaningful_prompt(cls,value):
        value=value.strip()
        if len(value)<3: raise ValueError('Prompt must contain at least three characters')
        return value

class Listing(Mutation):
    object_id: UUID
    version: int = Field(ge=1)
    price: int = Field(ge=1,le=10000)
