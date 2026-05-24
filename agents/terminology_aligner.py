"""
术语对齐Agent
功能：基于正畸领域标准化术语库完成专业术语的精准对齐
使用向量检索增强生成（RAG）替代部分推理
"""

import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from utils.llm_client import MixedLLMClient
from utils.rag_retriever import OrthodonticsRAGRetriever
from utils.logger import agent_logger


@dataclass
class TermAlignment:
    """术语对齐结果"""
    original_term: str  # 原文术语
    aligned_term: str   # 对齐后的标准术语
    chinese_term: str   # 中文译名
    confidence: float   # 置信度 0-1
    definition: str     # 定义
    synonyms: List[str] # 同义词
    context: str        # 上下文


class TerminologyAlignerAgent:
    """术语对齐Agent"""
    
    def __init__(self, llm_client: MixedLLMClient, 
                 rag_retriever: OrthodonticsRAGRetriever,
                 use_rag_first: bool = True):
        """
        初始化术语对齐Agent
        
        Args:
            llm_client: 混合LLM客户端
            rag_retriever: RAG检索器
            use_rag_first: 是否优先使用RAG检索
        """
        self.llm_client = llm_client
        self.rag_retriever = rag_retriever
        self.use_rag_first = use_rag_first
        self.terminology_model = llm_client.get_model('terminology')
        
        agent_logger.info("术语对齐Agent初始化完成")
    
    async def align_terminology(self, text: str, 
                               context_window: int = 3) -> Dict[str, TermAlignment]:
        """
        对文本进行术语对齐
        
        Args:
            text: 输入文本
            context_window: 上下文窗口（前后文句数）
        
        Returns:
            术语对齐结果字典
        """
        agent_logger.info("开始术语对齐...")
        
        try:
            # 第一步：提取候选术语
            candidate_terms = await self._extract_candidate_terms(text)
            agent_logger.info(f"提取候选术语 {len(candidate_terms)} 个")
            
            # 第二步：批量检索和对齐
            aligned_terms = await self._batch_align_terms(
                candidate_terms, text, context_window
            )
            
            agent_logger.info(f"✓ 术语对齐完成，已对齐 {len(aligned_terms)} 个术语")
            return aligned_terms
        
        except Exception as e:
            agent_logger.error(f"术语对齐失败: {e}")
            raise
    
    async def _extract_candidate_terms(self, text: str) -> List[str]:
        """
        从文本中提取候选术语
        
        Args:
            text: 输入文本
        
        Returns:
            候选术语列表
        """
        # 使用LLM提取专业术语
        prompt = f"""从以下正畸医学文本中提取所有专业术语（英文或中文）。
仅返回术语列表，用逗号分隔，不要其他内容。

文本：
{text[:2000]}

术语列表："""
        
        try:
            response = await self.terminology_model.ainvoke({
                "text": text[:2000]
            })
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析术语列表
            terms = [t.strip() for t in response_text.split(',') if t.strip()]
            
            return terms[:50]  # 限制数量以提高效率
        
        except Exception as e:
            agent_logger.warning(f"术语提取失败: {e}")
            return []
    
    async def _batch_align_terms(self, 
                                 terms: List[str], 
                                 text: str,
                                 context_window: int = 3) -> Dict[str, TermAlignment]:
        """
        批量对齐术语
        
        Args:
            terms: 候选术语列表
            text: 原始文本
            context_window: 上下文窗口
        
        Returns:
            对齐结果
        """
        aligned_terms = {}
        
        for term in terms:
            try:
                # 优先使用RAG检索
                if self.use_rag_first:
                    alignment = await self._align_with_rag(term, text, context_window)
                else:
                    alignment = await self._align_with_llm(term, text, context_window)
                
                if alignment:
                    aligned_terms[term] = alignment
            
            except Exception as e:
                agent_logger.warning(f"术语 '{term}' 对齐失败: {e}")
                continue
        
        return aligned_terms
    
    async def _align_with_rag(self, term: str, text: str, 
                             context_window: int = 3) -> Optional[TermAlignment]:
        """
        使用RAG进行术语对齐
        
        Args:
            term: 术语
            text: 原始文本
            context_window: 上下文窗口
        
        Returns:
            对齐结果
        """
        try:
            # 从向量库检索相关术语
            retrieved_terms = self.rag_retriever.retrieve_term(term, top_k=3)
            
            if not retrieved_terms:
                return None
            
            # 取置信度最高的结果
            best_match = retrieved_terms[0]
            
            # 获取上下文
            context = self._extract_context(text, term, context_window)
            
            alignment = TermAlignment(
                original_term=term,
                aligned_term=best_match.get('english', term),
                chinese_term=best_match.get('chinese', ''),
                confidence=min(best_match.get('similarity_score', 0.5), 1.0),
                definition=best_match.get('definition', ''),
                synonyms=best_match.get('synonyms', []),
                context=context
            )
            
            return alignment
        
        except Exception as e:
            agent_logger.warning(f"RAG对齐失败: {e}")
            return None
    
    async def _align_with_llm(self, term: str, text: str,
                             context_window: int = 3) -> Optional[TermAlignment]:
        """
        使用LLM进行术语对齐
        
        Args:
            term: 术语
            text: 原始文本
            context_window: 上下文窗口
        
        Returns:
            对齐结果
        """
        try:
            context = self._extract_context(text, term, context_window)
            
            prompt = f"""作为正畸医学专家，请对齐以下术语。

术语: {term}
上下文: {context}

请返回JSON格式，包含：
- aligned_term: 标准英文术语
- chinese_term: 中文译名
- definition: 定义
- synonyms: 同义词列表（JSON数组）
- confidence: 置信度（0-1）

只返回JSON，不要其他内容。"""
            
            response = await self.terminology_model.ainvoke({"text": prompt})
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 尝试解析JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                
                alignment = TermAlignment(
                    original_term=term,
                    aligned_term=result.get('aligned_term', term),
                    chinese_term=result.get('chinese_term', ''),
                    confidence=result.get('confidence', 0.5),
                    definition=result.get('definition', ''),
                    synonyms=result.get('synonyms', []),
                    context=context
                )
                
                return alignment
            
            return None
        
        except Exception as e:
            agent_logger.warning(f"LLM对齐失败: {e}")
            return None
    
    def _extract_context(self, text: str, term: str, 
                        window: int = 3) -> str:
        """
        提取术语的上下文
        
        Args:
            text: 原始文本
            term: 术语
            window: 前后文句数
        
        Returns:
            上下文
        """
        sentences = text.split('.')
        
        # 查找包含术语的句子
        for i, sentence in enumerate(sentences):
            if term.lower() in sentence.lower():
                # 提取前后文
                start = max(0, i - window)
                end = min(len(sentences), i + window + 1)
                
                context = '. '.join(sentences[start:end])
                return context[:500]  # 限制长度
        
        return ""
    
    def generate_terminology_glossary(self, 
                                     aligned_terms: Dict[str, TermAlignment]) -> str:
        """
        生成术语表
        
        Args:
            aligned_terms: 对齐的术语字典
        
        Returns:
            术语表（Markdown格式）
        """
        glossary = "## 术语表\n\n"
        glossary += "| 英文 | 中文 | 定义 | 同义词 |\n"
        glossary += "|------|------|------|--------|\n"
        
        for original, alignment in sorted(aligned_terms.items()):
            synonyms_str = ', '.join(alignment.synonyms) if alignment.synonyms else '-'
            glossary += f"| {alignment.aligned_term} | {alignment.chinese_term} | {alignment.definition[:50]} | {synonyms_str} |\n"
        
        return glossary


async def create_terminology_aligner(llm_client: MixedLLMClient,
                                     rag_retriever: OrthodonticsRAGRetriever) -> TerminologyAlignerAgent:
    """工厂函数：创建术语对齐Agent"""
    return TerminologyAlignerAgent(llm_client, rag_retriever)
