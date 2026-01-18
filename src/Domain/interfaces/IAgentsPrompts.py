from abc import ABC,abstractmethod


class IAgentPrompts(ABC):
    @abstractmethod
    def get_flow_decision_prompt():...
    @abstractmethod
    def get_response_prompt():...