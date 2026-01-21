from abc import ABC,abstractmethod


from typing import List,Dict,Any

from src.Domain import ConversationContext,ResponsePackageEntity



class IDecisionService(ABC):
    @abstractmethod
    def apply_flow_state(self,decision:dict,context:ConversationContext,sender_id:str):...
    @abstractmethod
    def prepare_tool_params(self, raw_params: Dict[str, Any], context: ConversationContext) -> Dict[str, Any]:...
    @abstractmethod
    def process_tool_outputs(self, tool_results: List[Dict[str, Any]], context: ConversationContext, package: ResponsePackageEntity):...