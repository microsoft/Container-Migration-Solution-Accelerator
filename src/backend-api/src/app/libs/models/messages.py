from pydantic import BaseModel

class ProcessStartQueueMessage(BaseModel):
    process_id: str
    user_id: str

    def to_base64(self) -> str:
        """
        Convert the response to a base64 encoded string.
        This is useful for creating queue message.
        """
        import base64

        return base64.b64encode(self.model_dump_json().encode()).decode()