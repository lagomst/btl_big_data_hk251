import os
# from .path_rag.PathRAG import PathRAG
# from .path_rag.base import QueryParam
# from .path_rag.llm import gpt_4o_mini_complete

from .light_rag.lightrag import LightRAG
from .light_rag.base import QueryParam as LightQueryParam
from .light_rag.llm.openai import gpt_4o_mini_complete, gpt_4o_complete, openai_embed
from .light_rag.kg.shared_storage import initialize_pipeline_status
from .light_rag.utils import TokenTracker, setup_logger
from .light_rag.base import DocStatus

import time
import openai
import os

from .commons import get_dict_except_blacklist
from .config import settings
from pathlib import Path
import shutil
from .utils import gen_html_graph
from core.models import InsertResponse, LimitTracker, ModelDetail

from functools import partial
from typing import Any
from dataclasses import asdict

KNOWLEDGE_DIR = Path('./knowledges').resolve()

LLM_MODEL_USED = settings.LLM_MODEL
MAX_BUFFER_LENGTH = settings.MAX_BUFFER_LENGTH
LLM_MODEL_FUNC_MAP: dict[str,Any] = {
    'gpt-4o' : gpt_4o_mini_complete,
    'gpt-4o-mini': gpt_4o_mini_complete
}

class ManagerRAG():
    # managing rag usage and knowledges instance
    def __init__(self):
        self._last_used_tokens: int = 0
        self._tokens_used: list[int] = []
        self._token_tracker = TokenTracker(owner=self)
        self._query_param = LightQueryParam(
            mode="hybrid",
            stream=True,
        )
        self._api_tier: str = None
        self._model_used: str = None
    
    async def create_isntance(self, knowledge, kg_path, 
        llm_model: str = "gpt-4o-mini",
        api_tier: str = "standard"
    ):
        openai.log = "debug"

        WORKING_DIR = KNOWLEDGE_DIR / kg_path

        os.environ["OPENAI_API_KEY"] = settings.LLM_API_KEY
        
        os.makedirs(WORKING_DIR, exist_ok=True)

        # As per LightRAG doc,
        # one should write their own llm_model_func
        if not llm_model:
            model_used = gpt_4o_mini_complete
            self._model_used = 'gpt-4o-mini'
        else:
            model_used = LLM_MODEL_FUNC_MAP.get(llm_model, gpt_4o_mini_complete)
            self._model_used = llm_model 
            
        self._api_tier = api_tier # string
        self.rag = await self.initialize_rag(knowledge_base=knowledge, llm_model=model_used, workspace=kg_path)
        return self
        
    async def initialize_rag(self, llm_model, knowledge_base: str, work_dir="./rag-storage", workspace=""):
        """
        work_dir: directory where cache and temp files are stored
        store_dir: directory where data is stored
        """
        rag = LightRAG(
            working_dir=work_dir,
            workspace=workspace,
            embedding_func=openai_embed,
            llm_model_func=partial(llm_model, token_tracker=self._token_tracker),
            embedding_func_max_async=settings.EMBEDDING_FUNC_MAX_ASYNC,
            embedding_batch_num=settings.EMBEDDING_BATCH_NUM,
            _knowledge_base=knowledge_base
        )

        await rag.initialize_storages()
        #await initialize_pipeline_status()
        from core.light_rag.kg import shared_storage
        assert shared_storage._update_flags is not None
        return rag


    async def get_knowledges() -> list[str]:
        knowledges = [p.name for p in list(KNOWLEDGE_DIR.glob('*'))]
        return knowledges
    
    async def load_knowledges():
        rags = {}
        knowledges = await ManagerRAG.get_knowledges() 

        print(f'\n*** {knowledges=}')
    
        for knowledge in knowledges :
            working_dir=KNOWLEDGE_DIR / knowledge
            print(f'\n*** {working_dir=}')
            rags[knowledge] = await ManagerRAG().create_isntance(knowledge, working_dir, settings.LLM_MODEL)

        return rags 

    async def create_knowledge(name):
        knowledges = await ManagerRAG.get_knowledges()
        if  name in knowledges:
            raise Exception(f'Knowledge {name} is existed!')   
        
        store_dir=KNOWLEDGE_DIR/name
        return await ManagerRAG().create_isntance(name, store_dir, settings.LLM_MODEL)     
    
    async def gen_html_graph(knowledge_name):
        return gen_html_graph(KNOWLEDGE_DIR / knowledge_name)
        
    async def delete_knowledge(self, name):
        knowledges = await ManagerRAG.get_knowledges()
        if name not in knowledges:
            raise Exception(f'Knowledge {name} is not exist!')   
        
        # Delete every document related to it
        docs = await self.search_docs()
        for doc_id, doc_obj in docs.items():
            res = await self.rag.adelete_by_doc_id(doc_id)
        
        working_dir=KNOWLEDGE_DIR/name
        if working_dir.exists() and working_dir.is_dir():
            shutil.rmtree(working_dir) 
    
    async def get_model_from_knowledge(self):
        return ModelDetail(
            model_used=self._model_used,
            api_tier=self._api_tier
        )
    
    async def estimate_tokens(self, text):
        # TODO: give a better estimation, 
        # Currently return token size of text
        tokenizer = self.rag.tokenizer
        tokens = len(tokenizer.encode(text))
        return tokens
    
    async def get_doc_by_id(self, doc_id):
        doc_status = await self.rag.aget_docs_by_ids(doc_id)
        return doc_status.get(doc_id, {})
    
    async def get_chunks_from_ids(self, chunk_ids: list[str]):
        return self.rag.chunks_vdb.get_by_ids(chunk_ids)
                    
    async def ainsert(self, text, filename: str, file_paths: str, limit_tracker: LimitTracker = None):
        # print(f"Sanity check: {filename=}, {file_paths=} ")
        if limit_tracker:
            self.set_tokens_limit(limit_tracker)
        start = time.time()
        error_msg = None
        try:
            # Let RAG process texts
            await self.rag.ainsert(text, ids=filename, file_paths=file_paths)
             # Check document status in the pipeline
            doc_status = await self.get_doc_by_id(filename)
            final_status = doc_status.get("status")
            if final_status == DocStatus.FAILED:
                error = doc_status.get("error")
                raise RuntimeError(error)
        except Exception as e:
            error_msg = f"Error during insert: {e}"
        
        end = time.time()
        
        tokens_used = None
        if self._token_tracker:
            tokens_used = self._token_tracker.get_usage()
            self._token_tracker.reset()
        return InsertResponse(
            error=error_msg,
            time=end-start,
            tokens_used=tokens_used,
            files=None,
            model_used=self._model_used,
            api_tier=self._api_tier
        )
    
    async def aquery(self, question, stream=False, limit_tracker: LimitTracker = None):
        llm_model_func = self.rag.llm_model_func
        query_param = LightQueryParam(
            mode="hybrid",
            stream=stream,
            model_func = llm_model_func
        )
        if limit_tracker:
            self.set_tokens_limit(limit_tracker)
        # print(f"LLM object used: {self.rag.llm_model_func} vs {partial(gpt_4o_mini_complete, token_tracker=self._token_tracker)}", )
        start = time.time()
        error = None
        result = None
        try:
            # Let RAG handle question
            result = await self.rag.aquery(question, param=query_param)
        except Exception as e:
            error = str(e)
        end = time.time() 
        # print(f'***Result {result=}') # output LightRAG.aquery at 0x...
        is_aiter = hasattr(result, "__aiter__") if result else False
        usage = self._token_tracker.get_usage()
        data = {
            "is_aiter": is_aiter,
            "time": end - start,
            "tokens_used": usage,
            "content": result,
            "error": error
        }
        
        self._token_tracker.reset()
        return data

    async def adelete_by_filename(self, filename: str):
        # Get doc datas:
        doc_data = await self.get_doc_by_id(doc_id=filename)
        delete_result = await self.rag.adelete_by_doc_id(filename)
        # await self.rag.aclear_cache()
        return asdict(delete_result)
    
    async def get_docs_by_status(self, status: DocStatus | str, blacklist=None) -> dict[str, Any]:
        if isinstance(status, str):
            search_status = DocStatus(status)
        elif isinstance(status, DocStatus):
            search_status = status
        else:
            raise ValueError("Invalid status type!")
        docs = await self.rag.get_docs_by_status(search_status)
        result = {}
        for doc_id, doc_status_obj in docs.items():
            doc_data = asdict(doc_status_obj)
            if blacklist:
                doc_data = get_dict_except_blacklist(doc_data, blacklist)
            result[doc_id] = doc_data
        return result
    
    async def get_all_docs(self, blacklist=None) -> dict[str, Any]:
        result = {}
        for key in DocStatus:
            docs = await self.get_docs_by_status(key, blacklist)
            print(f"{docs=}")
            result.update(docs)
        
        return result
    
    async def search_docs(self, *, 
        prefix: str = None, 
        filter: str = None, 
        status: str = None, 
        path: str = None,
        blacklist: list | tuple | set = None
    ) -> dict[str, Any]:
        print(f"Sanity check: {prefix=}, {filter=}, {status=}, {path=}")
        if status:
            docs = await self.get_docs_by_status(status, blacklist)
        else:
            docs = await self.get_all_docs(blacklist)

        query = {}
        if prefix or filter or path:
            for doc_name in docs.keys():
                if prefix and not doc_name.startswith(prefix):
                    continue
                if filter and doc_name.find(filter) < 0:
                    continue
                # Contain path inside file_paths fields
                if path and docs[doc_name].get("file_path").find(path) < 0:
                    continue
                query[doc_name] = docs[doc_name]
        else:
            query = docs
        
        # print(f"{query=}")
             
        return query
    
    def set_tokens_limit(self, limit_tracker: LimitTracker):
        # IMPORTANT:
        # For the limit to work, llm_model_func MUST BE CONFIGURED to check for the limit.
        if not limit_tracker:
            raise ValueError("Invalid limit_tracker!")
        self._token_tracker.set_limit(
            limit_tracker.tokens_limit,
            limit_tracker.money_limit,
            limit_tracker.price_1m_prompt,
            limit_tracker.price_1m_completion
        )