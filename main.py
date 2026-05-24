"""
主程序入口
多Agent协作的文献解析系统
"""

import asyncio
import argparse
from pathlib import Path

from utils.llm_client import MixedLLMClient
from utils.rag_retriever import OrthodonticsRAGRetriever
from agents.structure_parser import create_structure_parser
from agents.terminology_aligner import create_terminology_aligner
from agents.reasoning_agent import create_reasoning_agent
from utils.logger import system_logger


class OrthoLiteratureAnalysisSystem:
    """正畸文献分析系统"""
    
    def __init__(self):
        """初始化系统"""
        system_logger.info("=" * 60)
        system_logger.info("正畸领域多Agent智能文献解析系统启动")
        system_logger.info("=" * 60)
        
        # 初始化LLM客户端
        self.llm_client = MixedLLMClient()
        system_logger.info(f"可用模型: {self.llm_client.get_available_models()}")
        
        # 初始化RAG检索器
        try:
            self.rag_retriever = OrthodonticsRAGRetriever(
                knowledge_dir='./knowledge'
            )
            system_logger.info(f"术语库加载完成: {self.rag_retriever.get_stats()}")
        except Exception as e:
            system_logger.warning(f"RAG检索器初始化失败: {e}")
            self.rag_retriever = None
    
    async def analyze_paper(self, input_file: str, output_file: str = None):
        """
        分析论文
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
        """
        try:
            # 读取输入文件
            system_logger.info(f"读取输入文件: {input_file}")
            with open(input_file, 'r', encoding='utf-8') as f:
                document_text = f.read()
            
            system_logger.info(f"文档大小: {len(document_text)} 字符")
            
            # 第一步：文献结构解析
            system_logger.info("\n[阶段1] 文献结构解析...")
            structure_parser = await create_structure_parser(self.llm_client)
            paper_structure = await structure_parser.parse_document(document_text)
            
            system_logger.info(f"论文标题: {paper_structure.title}")
            system_logger.info(f"论文作者: {paper_structure.authors}")
            
            # 第二步：术语对齐
            system_logger.info("\n[阶段2] 术语对齐...")
            if self.rag_retriever:
                terminology_aligner = await create_terminology_aligner(
                    self.llm_client, self.rag_retriever
                )
                # 对摘要进行术语对齐
                if paper_structure.abstract:
                    aligned_terms = await terminology_aligner.align_terminology(
                        paper_structure.abstract
                    )
                    system_logger.info(f"对齐术语数: {len(aligned_terms)}")
                    terminology_glossary = terminology_aligner.generate_terminology_glossary(aligned_terms)
            else:
                system_logger.warning("跳过术语对齐（RAG不可用）")
                terminology_glossary = None
            
            # 第三步：长链推理和翻译
            system_logger.info("\n[阶段3] 长链推理与翻译...")
            reasoning_agent = await create_reasoning_agent(self.llm_client)
            
            # 转换结构为字典
            paper_dict = {
                'title': paper_structure.title,
                'abstract': paper_structure.abstract,
                'introduction': paper_structure.introduction,
                'methods': paper_structure.methods,
                'results': paper_structure.results,
                'discussion': paper_structure.discussion,
                'conclusion': paper_structure.conclusion,
            }
            
            # 生成综合翻译报告
            comprehensive_report = await reasoning_agent.generate_comprehensive_translation(
                paper_dict,
                terminology_glossary
            )
            
            # 生成Markdown报告
            logic_chain = comprehensive_report.get('logic_chain')
            final_report = reasoning_agent.generate_markdown_report(
                comprehensive_report,
                logic_chain
            )
            
            # 保存输出
            if output_file is None:
                output_file = 'translated_paper.md'
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(final_report)
            
            system_logger.info(f"\n✓ 分析完成！输出文件: {output_file}")
            
            return final_report
        
        except Exception as e:
            system_logger.error(f"分析失败: {e}", exc_info=True)
            raise


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='正畸领域多Agent智能文献解析系统'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='输入论文文件路径'
    )
    parser.add_argument(
        '--output', '-o',
        default='translated_paper.md',
        help='输出文件路径（默认: translated_paper.md）'
    )
    
    args = parser.parse_args()
    
    # 创建系统实例
    system = OrthoLiteratureAnalysisSystem()
    
    # 分析论文
    await system.analyze_paper(args.input, args.output)


if __name__ == '__main__':
    asyncio.run(main())
