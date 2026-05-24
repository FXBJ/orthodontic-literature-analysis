"""
长链推理Agent
功能：梳理研究的完整逻辑链，完成全文标准化翻译，补充专业术语注释
使用高端模型（GPT-4/Claude）进行深层推理
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass

from utils.llm_client import MixedLLMClient
from utils.logger import agent_logger


@dataclass
class ResearchLogicChain:
    """研究逻辑链"""
    research_question: str          # 研究问题
    hypothesis: str                 # 假设
    methodology_summary: str        # 方法论摘要
    key_findings: List[str]         # 关键发现
    conclusions: List[str]          # 结论
    implications: List[str]         # 意义


class ReasoningAgent:
    """长链推理Agent"""
    
    def __init__(self, llm_client: MixedLLMClient):
        """
        初始化长链推理Agent
        
        Args:
            llm_client: 混合LLM客户端
        """
        self.llm_client = llm_client
        self.reasoning_model = llm_client.get_model('reasoning')
        
        agent_logger.info("长链推理Agent初始化完成")
    
    async def translate_to_chinese(self, english_text: str,
                                  terminology_glossary: Dict = None) -> str:
        """
        将文本翻译为中文，同时补充术语注释
        
        Args:
            english_text: 英文文本
            terminology_glossary: 术语表字典
        
        Returns:
            中文翻译文本
        """
        agent_logger.info("开始文本翻译...")
        
        try:
            # 准备术语注释提示
            terminology_hint = ""
            if terminology_glossary:
                terminology_hint = self._prepare_terminology_hints(terminology_glossary)
            
            prompt = f"""你是一名正畸医学领域的专业翻译，请将以下英文学术文本翻译成中文。

翻译要求：
1. 保持学术严谨性和医学准确性
2. 使用标准的正畸医学术语
3. 保持原文的逻辑关系和论述结构
4. 对关键术语进行标注（格式: 中文术语[英文术语]）
5. 如果遇到复杂的医学概念，添加简洁的括号注释

{terminology_hint}

英文文本：
{english_text}

请提供高质量的中文翻译："""
            
            response = await self.reasoning_model.ainvoke({"text": prompt})
            translation = response.content if hasattr(response, 'content') else str(response)
            
            agent_logger.info("✓ 文本翻译完成")
            return translation
        
        except Exception as e:
            agent_logger.error(f"翻译失败: {e}")
            raise
    
    async def extract_logic_chain(self, paper_structure: Dict) -> ResearchLogicChain:
        """
        从论文结构中提取研究逻辑链
        
        Args:
            paper_structure: 论文结构字典
        
        Returns:
            研究逻辑链
        """
        agent_logger.info("开始逻辑链提取...")
        
        try:
            # 组合关键章节作为输入
            combined_text = f"""
标题: {paper_structure.get('title', '')}

摘要:
{paper_structure.get('abstract', '')}

方法:
{paper_structure.get('methods', '')}

结果:
{paper_structure.get('results', '')}

讨论:
{paper_structure.get('discussion', '')}

结论:
{paper_structure.get('conclusion', '')}
"""
            
            prompt = f"""作为医学研究专家，请分析以下论文的逻辑链。

论文信息：
{combined_text}

请提取以下信息，返回JSON格式：
{{
  "research_question": "研究问题是什么？",
  "hypothesis": "主要假设是什么？",
  "methodology_summary": "研究方法的简要总结",
  "key_findings": ["发现1", "发现2", "发现3"],
  "conclusions": ["结论1", "结论2"],
  "implications": ["意义或应用1", "意义或应用2"]
}}

只返回JSON，不要其他内容。"""
            
            response = await self.reasoning_model.ainvoke({"text": prompt})
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                result = json.loads(json_match.group())
                
                logic_chain = ResearchLogicChain(
                    research_question=result.get('research_question', ''),
                    hypothesis=result.get('hypothesis', ''),
                    methodology_summary=result.get('methodology_summary', ''),
                    key_findings=result.get('key_findings', []),
                    conclusions=result.get('conclusions', []),
                    implications=result.get('implications', [])
                )
                
                agent_logger.info("✓ 逻辑链提取完成")
                return logic_chain
            else:
                raise ValueError("无法解析LLM响应")
        
        except Exception as e:
            agent_logger.error(f"逻辑链提取失败: {e}")
            raise
    
    def _prepare_terminology_hints(self, glossary: Dict) -> str:
        """
        准备术语注释提示
        
        Args:
            glossary: 术语表字典
        
        Returns:
            术语提示文本
        """
        hints = "\n关键术语对照表:\n"
        for english, chinese_info in list(glossary.items())[:20]:  # 限制数量
            if isinstance(chinese_info, dict):
                chinese = chinese_info.get('chinese_term', '')
            else:
                chinese = str(chinese_info)
            
            hints += f"- {english} = {chinese}\n"
        
        return hints
    
    async def generate_comprehensive_translation(self,
                                                paper_structure: Dict,
                                                terminology_glossary: Dict = None) -> Dict:
        """
        生成综合翻译报告
        
        Args:
            paper_structure: 论文结构
            terminology_glossary: 术语表
        
        Returns:
            包含翻译和注释的完整报告
        """
        agent_logger.info("生成综合翻译报告...")
        
        try:
            report = {
                'title': paper_structure.get('title', ''),
                'translated_title': await self._translate_section(paper_structure.get('title', ''), terminology_glossary),
                'sections': {}
            }
            
            # 翻译各个章节
            sections_to_translate = ['abstract', 'introduction', 'methods', 'results', 'discussion', 'conclusion']
            
            for section_name in sections_to_translate:
                if section_name in paper_structure and paper_structure[section_name]:
                    agent_logger.info(f"翻译 {section_name} 章节...")
                    
                    report['sections'][section_name] = {
                        'original': paper_structure[section_name][:500],  # 原文摘录
                        'translated': await self._translate_section(
                            paper_structure[section_name],
                            terminology_glossary
                        )
                    }
            
            # 提取逻辑链
            report['logic_chain'] = await self.extract_logic_chain(paper_structure)
            
            agent_logger.info("✓ 综合翻译报告生成完成")
            return report
        
        except Exception as e:
            agent_logger.error(f"综合翻译失败: {e}")
            raise
    
    async def _translate_section(self, section_text: str, 
                                terminology_glossary: Dict = None) -> str:
        """
        翻译单个章节
        
        Args:
            section_text: 章节文本
            terminology_glossary: 术语表
        
        Returns:
            翻译后的文本
        """
        if not section_text:
            return ""
        
        # 对长文本进行分段翻译
        if len(section_text) > 2000:
            # 按句子分段
            sentences = section_text.split('.')
            translated_parts = []
            
            for i in range(0, len(sentences), 5):
                chunk = '.'.join(sentences[i:i+5])
                if chunk.strip():
                    translated = await self.translate_to_chinese(chunk, terminology_glossary)
                    translated_parts.append(translated)
            
            return '\n'.join(translated_parts)
        else:
            return await self.translate_to_chinese(section_text, terminology_glossary)
    
    def generate_markdown_report(self, comprehensive_report: Dict,
                                logic_chain: ResearchLogicChain) -> str:
        """
        生成Markdown格式的完整报告
        
        Args:
            comprehensive_report: 综合翻译报告
            logic_chain: 研究逻辑链
        
        Returns:
            Markdown格式的报告
        """
        markdown = f"""# {comprehensive_report.get('title', '')}

## 中文标题
{comprehensive_report.get('translated_title', '')}

---

## 研究逻辑链

### 研究问题
{logic_chain.research_question}

### 假设
{logic_chain.hypothesis}

### 方法论
{logic_chain.methodology_summary}

### 关键发现
"""
        
        for finding in logic_chain.key_findings:
            markdown += f"- {finding}\n"
        
        markdown += "\n### 主要结论\n"
        for conclusion in logic_chain.conclusions:
            markdown += f"- {conclusion}\n"
        
        markdown += "\n### 研究意义\n"
        for implication in logic_chain.implications:
            markdown += f"- {implication}\n"
        
        markdown += "\n---\n\n## 详细翻译\n"
        
        for section_name, content in comprehensive_report.get('sections', {}).items():
            markdown += f"\n### {section_name.upper()}\n"
            markdown += f"\n**原文摘录:**\n{content.get('original', '')[:200]}...\n\n"
            markdown += f"**中文翻译:**\n{content.get('translated', '')}\n\n"
        
        return markdown


async def create_reasoning_agent(llm_client: MixedLLMClient) -> ReasoningAgent:
    """工厂函数：创建长链推理Agent"""
    return ReasoningAgent(llm_client)
