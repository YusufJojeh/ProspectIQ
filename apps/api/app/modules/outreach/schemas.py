from pydantic import BaseModel


class OutreachMessageResult(BaseModel):
    subject: str
    message: str

