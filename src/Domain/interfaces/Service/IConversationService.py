from abc import ABC,abstractmethod


class IConversationService(ABC):
    @abstractmethod
    async def process_message(
                                self,
                                sender_id:str,
                                instance:str,
                                channel:str, 
                                text:str
                            ):...
