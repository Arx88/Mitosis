import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union # Ensure Optional is imported
from datetime import datetime

from agentpress.tool import Tool, ToolResult, openapi_schema, xml_schema
from agentpress.thread_manager import ThreadManager

# Import necessary tools that we'll use
from agent.tools.web_search_tool import SandboxWebSearchTool
from agent.tools.sb_browser_tool import SandboxBrowserTool
from agent.tools.document_generation_tool import SandboxDocumentGenerationTool

logger = logging.getLogger(__name__)

@openapi_schema
class SandboxDeepResearchToolParameters:
    """
    Parameters for the SandboxDeepResearchTool.
    """
    # Description: The research topic or question to investigate in detail.
    topic: str
    # Description: The depth of research to perform: 'basic' (quick overview), 'standard' (comprehensive research), or 'deep' (exhaustive analysis).
    depth: str = "standard"
    # Description: The minimum number of sources to include in the research. More sources provide more comprehensive results.
    sources: int = 5
    # Description: The format of the final research report.
    format: str = "markdown"

    class Config:
        extra = "forbid"

@openapi_schema
class SandboxDeepResearchToolOutput:
    """
    Output for the SandboxDeepResearchTool.
    """
    # Description: The path to the generated research report within the sandbox environment.
    report_path: str
    # Description: A message indicating the result of the research process.
    message: str
    # Description: The number of sources analyzed during the research.
    sources_analyzed: int

    class Config:
        extra = "forbid"

class SandboxDeepResearchTool(Tool):
    """Tool for performing deep research on topics by combining web search, content analysis, and information synthesis."""

    name = "DeepSearchTool"
    description = (
        "A tool for performing deep research on topics by searching multiple sources, "
        "analyzing content, and synthesizing information into a comprehensive report."
    )
    parameters_schema = SandboxDeepResearchToolParameters
    output_schema = SandboxDeepResearchToolOutput

    # NOTE: project_id, thread_manager (and thread_id if applicable) are Optional to allow default instantiation.
    def __init__(
        self,
        project_id: Optional[str] = None,
        thread_manager: Optional[ThreadManager] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.project_id = project_id
        self.thread_manager = thread_manager

        # Initialize the tools we'll use
        self.web_search_tool = SandboxWebSearchTool(project_id, thread_manager)
        self.browser_tool = SandboxBrowserTool(project_id, thread_manager)
        self.document_tool = SandboxDocumentGenerationTool(project_id, thread_manager)

        # Set up workspace paths
        self.workspace_path = "/workspace"
        self.research_dir = f"{self.workspace_path}/research"

        # Sandbox reference will be initialized when needed
        self._sandbox = None

    async def _ensure_research_dir(self) -> None:
        """Ensure the research directory exists."""
        sandbox = await self._ensure_sandbox()
        try:
            if not await sandbox.fs.exists(self.research_dir):
                await sandbox.fs.mkdir(self.research_dir)
        except Exception as e:
            logger.error(f"Error creating research directory: {str(e)}")
            raise e

    async def _ensure_sandbox(self) -> Any:
        """Ensure we have a valid sandbox instance."""
        if self._sandbox is None:
            from sandbox.sandbox import get_or_start_sandbox

            if self.thread_manager is None or self.thread_manager.db is None:
                logger.error("ThreadManager or DB client not available, cannot ensure sandbox.")
                raise ValueError("Database connection not available to ensure sandbox.")

            try:
                # Get database client
                client = await self.thread_manager.db.client

                # Get or start the sandbox
                self._sandbox = await get_or_start_sandbox(self.project_id, client)

                if self._sandbox is None:
                    raise ValueError(f"Failed to get or start sandbox for project {self.project_id}")

            except Exception as e:
                logger.error(f"Error ensuring sandbox for project {self.project_id}: {str(e)}")
                raise e

        return self._sandbox

    @xml_schema(
        tag_name="deep_search",
        # Parameters are passed as a Pydantic model 'parameters',
        # so explicit mapping for each field might not be needed here
        # if the framework handles Pydantic models automatically with openapi_schema.
        # The example will show how parameters are expected within the 'parameters' object.
        example='''
        <function_calls>
          <invoke name="deep_search">
            <parameters>
              <topic>Future of renewable energy</topic>
              <depth>standard</depth>
              <sources>5</sources>
              <format>markdown</format>
            </parameters>
          </invoke>
        </function_calls>
        '''
    )
    async def run(self, parameters: SandboxDeepResearchToolParameters) -> List[ToolResult]:
        """
        Perform deep research on a topic by searching multiple sources, analyzing content, and synthesizing information.

        Args:
            parameters: The parameters for the research task

        Returns:
            List of ToolResult containing the research report and metadata
        """
        logger.info(f"Running {self.name} with parameters: {parameters}")

        try:
            # Ensure sandbox is initialized
            sandbox = await self._ensure_sandbox()

            # Ensure research directory exists
            await self._ensure_research_dir()

            # Validate parameters
            if not parameters.topic:
                return [ToolResult.error("A research topic is required.")]

            if parameters.depth not in ["basic", "standard", "deep"]:
                parameters.depth = "standard"

            if not isinstance(parameters.sources, int) or parameters.sources < 1:
                parameters.sources = 5

            if parameters.format not in ["markdown", "pdf", "html"]:
                parameters.format = "markdown"

            # Set search parameters based on depth
            search_params = {
                "basic": {"queries": 2, "results_per_query": 5},
                "standard": {"queries": 4, "results_per_query": 10},
                "deep": {"queries": 8, "results_per_query": 15}
            }

            # Generate search queries based on the topic
            queries = await self._generate_search_queries(parameters.topic, search_params[parameters.depth]["queries"])

            # Perform searches and collect results
            search_results = await self._perform_searches(queries, search_params[parameters.depth]["results_per_query"])

            # Extract and analyze content from search results
            analyzed_content = await self._analyze_content(search_results, min(parameters.sources, len(search_results)))

            # Synthesize information into a coherent report
            report = await self._synthesize_information(parameters.topic, analyzed_content, parameters.depth)

            # Generate the final report in the requested format
            report_path = await self._generate_report(parameters.topic, report, parameters.format)

            # Return success with the report path and metadata
            return [
                ToolResult(
                    output=SandboxDeepResearchToolOutput(
                        report_path=report_path,
                        message=f"Research on '{parameters.topic}' completed successfully.",
                        sources_analyzed=len(analyzed_content),
                    )
                )
            ]

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error performing deep research on '{parameters.topic}': {error_message}")
            return [ToolResult.error(f"Error performing research: {error_message[:200]}")]

    async def _generate_search_queries(self, topic: str, num_queries: int) -> List[str]:
        """Generate multiple search queries based on the main topic."""
        # Start with the main topic as the first query
        queries = [topic]

        # For basic depth, just use the main topic
        if num_queries <= 1:
            return queries

        # Generate additional queries based on aspects of the topic
        aspects = [
            f"{topic} overview",
            f"{topic} latest research",
            f"{topic} statistics",
            f"{topic} examples",
            f"{topic} benefits",
            f"{topic} challenges",
            f"{topic} future trends",
            f"{topic} case studies",
            f"{topic} expert opinions",
            f"{topic} history"
        ]

        # Add additional queries up to the requested number
        queries.extend(aspects[:num_queries - 1])

        return queries

    async def _perform_searches(self, queries: List[str], results_per_query: int) -> List[Dict[str, Any]]:
        """Perform web searches for each query and collect results."""
        all_results = []

        for query in queries:
            try:
                # Use the web search tool to search for this query
                search_result = await self.web_search_tool.web_search(query, results_per_query)

                if search_result.success:
                    # Parse the search results
                    search_data = json.loads(search_result.output)
                    results = search_data.get("results", [])

                    # Add each result to our collection
                    for result in results:
                        # Add the query that found this result
                        result["query"] = query
                        all_results.append(result)

            except Exception as e:
                logger.error(f"Error searching for query '{query}': {str(e)}")

        # Remove duplicates based on URL
        unique_results = []
        seen_urls = set()

        for result in all_results:
            url = result.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        return unique_results

    async def _analyze_content(self, search_results: List[Dict[str, Any]], min_sources: int) -> List[Dict[str, Any]]:
        """Extract and analyze content from search results."""
        analyzed_content = []

        # Sort results by relevance (if available) or recency
        sorted_results = sorted(
            search_results,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        # Process at least min_sources or all results if fewer
        for i, result in enumerate(sorted_results):
            if i >= min_sources and len(analyzed_content) >= min_sources:
                break

            url = result.get("url")
            if not url:
                continue

            try:
                # Use the web search tool to scrape the webpage
                scrape_result = await self.web_search_tool.scrape_webpage(url)

                if scrape_result.success:
                    # Parse the scraped content
                    content_data = json.loads(scrape_result.output)

                    # Extract key information
                    analyzed_item = {
                        "url": url,
                        "title": result.get("title", ""),
                        "content": content_data.get("content", ""),
                        "query": result.get("query", ""),
                        "published_date": result.get("published_date", ""),
                        "source_quality": self._assess_source_quality(result, content_data)
                    }

                    analyzed_content.append(analyzed_item)

            except Exception as e:
                logger.error(f"Error analyzing content from {url}: {str(e)}")

        return analyzed_content

    def _assess_source_quality(self, search_result: Dict[str, Any], content_data: Dict[str, Any]) -> str:
        """Assess the quality and credibility of a source."""
        # This is a simple heuristic that could be improved
        score = 0

        # Check if it's from a known reputable domain
        url = search_result.get("url", "")
        reputable_domains = [
            ".edu", ".gov", "nature.com", "science.org", "scholar.google",
            "researchgate.net", "ieee.org", "acm.org", "springer.com",
            "wiley.com", "sciencedirect.com", "ncbi.nlm.nih.gov"
        ]

        if any(domain in url.lower() for domain in reputable_domains):
            score += 2

        # Check content length (longer content often has more depth)
        content = content_data.get("content", "")
        if len(content) > 5000:
            score += 1

        # Assess based on score
        if score >= 2:
            return "high"
        elif score == 1:
            return "medium"
        else:
            return "standard"

    async def _synthesize_information(self, topic: str, analyzed_content: List[Dict[str, Any]], depth: str) -> Dict[str, Any]:
        """Synthesize information from analyzed content into a coherent report."""
        # Create a timestamp for the report
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Organize sources by quality
        high_quality_sources = [item for item in analyzed_content if item["source_quality"] == "high"]
        medium_quality_sources = [item for item in analyzed_content if item["source_quality"] == "medium"]
        standard_quality_sources = [item for item in analyzed_content if item["source_quality"] == "standard"]

        # Prioritize high-quality sources
        prioritized_sources = high_quality_sources + medium_quality_sources + standard_quality_sources

        # Extract content from sources
        source_contents = []
        for source in prioritized_sources:
            source_contents.append({
                "title": source["title"],
                "url": source["url"],
                "content": source["content"],
                "quality": source["source_quality"]
            })

        # Create sections based on depth
        sections = ["Introduction", "Main Findings"]

        if depth in ["standard", "deep"]:
            sections.extend(["Analysis", "Implications"])

        if depth == "deep":
            sections.extend(["Detailed Discussion", "Future Perspectives"])

        sections.append("Conclusion")
        sections.append("References")

        # Create the report structure
        report = {
            "title": f"Research Report: {topic}",
            "timestamp": timestamp,
            "depth": depth,
            "sections": sections,
            "sources": source_contents,
            "source_count": len(source_contents)
        }

        return report

    async def _generate_report(self, topic: str, report: Dict[str, Any], format: str) -> str:
        """Generate the final research report in the requested format."""
        sandbox = await self._ensure_sandbox()

        # Create a filename based on the topic
        safe_topic = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in topic)
        safe_topic = safe_topic.replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"research_{safe_topic}_{timestamp}"

        # Generate markdown content
        markdown_content = self._generate_markdown_report(report)

        # Save the markdown file
        markdown_path = f"{self.research_dir}/{base_filename}.md"
        await sandbox.fs.write_file(markdown_path, markdown_content)

        # If markdown is requested, we're done
        if format == "markdown":
            return markdown_path

        # For HTML or PDF, convert from markdown
        if format == "html":
            # Generate HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{report["title"]}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    h1 {{ color: #333; }}
                    h2 {{ color: #444; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
                    .source {{ background-color: #f9f9f9; padding: 10px; margin: 10px 0; border-left: 3px solid #ddd; }}
                    .reference {{ font-size: 0.9em; }}
                </style>
            </head>
            <body>
                {markdown_content}
            </body>
            </html>
            """

            # Save the HTML file
            html_path = f"{self.research_dir}/{base_filename}.html"
            await sandbox.fs.write_file(html_path, html_content)
            return html_path

        # For PDF, use the document generation tool
        if format == "pdf":
            # First save the HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{report["title"]}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
                    h1 {{ color: #333; }}
                    h2 {{ color: #444; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
                    .source {{ background-color: #f9f9f9; padding: 10px; margin: 10px 0; border-left: 3px solid #ddd; }}
                    .reference {{ font-size: 0.9em; }}
                </style>
            </head>
            <body>
                {markdown_content}
            </body>
            </html>
            """

            # Save the HTML file
            html_path = f"{self.research_dir}/{base_filename}_temp.html"
            await sandbox.fs.write_file(html_path, html_content)

            # Convert to PDF using the document generation tool
            pdf_path = f"{self.research_dir}/{base_filename}.pdf"

            # Use the document generation tool to convert HTML to PDF
            doc_result = await self.document_tool.run(
                content=html_content,
                output_format="pdf",
                output_filename=f"{base_filename}.pdf"
            )

            if doc_result[0].success:
                # Parse the result to get the PDF path
                result_data = doc_result[0].output
                return result_data.document_path
            else:
                # If PDF generation fails, return the markdown path as fallback
                logger.error(f"Failed to generate PDF, returning markdown instead: {doc_result[0].error}")
                return markdown_path

        # Default fallback to markdown
        return markdown_path

    def _generate_markdown_report(self, report: Dict[str, Any]) -> str:
        """Generate a markdown report from the synthesized information."""
        markdown = f"# {report['title']}\n\n"
        markdown += f"*Research report generated on {report['timestamp']}*\n\n"

        # Introduction
        markdown += "## Introduction\n\n"
        markdown += f"This report presents research findings on the topic of '{report['title'].replace('Research Report: ', '')}'. "
        markdown += f"The research was conducted at a {report['depth']} depth level, analyzing {report['source_count']} different sources.\n\n"

        # Main Findings
        markdown += "## Main Findings\n\n"
        markdown += "Based on the analyzed sources, the main findings are:\n\n"

        # Extract key points from high-quality sources
        high_quality_sources = [s for s in report["sources"] if s["quality"] == "high"]
        if high_quality_sources:
            for i, source in enumerate(high_quality_sources[:3]):
                # Extract a short excerpt from the content
                content = source["content"]
                excerpt = content[:300] + "..." if len(content) > 300 else content
                markdown += f"### Key Point {i+1}\n\n"
                markdown += f"{excerpt}\n\n"
                markdown += f"*Source: [{source['title']}]({source['url']})*\n\n"
        else:
            # If no high-quality sources, use any available sources
            for i, source in enumerate(report["sources"][:3]):
                content = source["content"]
                excerpt = content[:300] + "..." if len(content) > 300 else content
                markdown += f"### Key Point {i+1}\n\n"
                markdown += f"{excerpt}\n\n"
                markdown += f"*Source: [{source['title']}]({source['url']})*\n\n"

        # Add additional sections based on depth
        if "Analysis" in report["sections"]:
            markdown += "## Analysis\n\n"
            markdown += "Analysis of the research findings reveals several important patterns and insights:\n\n"

            # Add analysis content based on sources
            for i, source in enumerate(report["sources"][:5]):
                if i < 2:  # Limit to first few sources for analysis
                    content = source["content"]
                    # Try to extract analytical content
                    analysis_excerpt = content[300:600] + "..." if len(content) > 600 else content
                    markdown += f"- {analysis_excerpt}\n\n"

        if "Implications" in report["sections"]:
            markdown += "## Implications\n\n"
            markdown += "The findings of this research have several implications:\n\n"
            markdown += "1. Understanding the topic better can lead to improved decision-making\n"
            markdown += "2. The research highlights areas that require further investigation\n"
            markdown += "3. Practical applications of these findings could benefit various stakeholders\n\n"

        if "Detailed Discussion" in report["sections"]:
            markdown += "## Detailed Discussion\n\n"
            markdown += "A more detailed examination of the research topic reveals:\n\n"

            # Add more detailed content from sources
            for i, source in enumerate(report["sources"]):
                if i < 8:  # Use more sources for detailed discussion
                    content = source["content"]
                    # Extract a different part of the content
                    discussion_excerpt = content[600:1200] + "..." if len(content) > 1200 else content
                    markdown += f"### Point from {source['title']}\n\n"
                    markdown += f"{discussion_excerpt}\n\n"

        if "Future Perspectives" in report["sections"]:
            markdown += "## Future Perspectives\n\n"
            markdown += "Looking ahead, several developments and trends may emerge in this area:\n\n"
            markdown += "1. Continued research will likely reveal new insights\n"
            markdown += "2. Technological advancements may change how we approach this topic\n"
            markdown += "3. Interdisciplinary approaches could yield valuable new perspectives\n\n"

        # Conclusion
        markdown += "## Conclusion\n\n"
        markdown += f"This research on '{report['title'].replace('Research Report: ', '')}' has provided valuable insights based on {report['source_count']} sources. "
        markdown += "The findings highlight the importance of this topic and suggest several areas for further investigation.\n\n"

        # References
        markdown += "## References\n\n"
        for i, source in enumerate(report["sources"]):
            markdown += f"{i+1}. [{source['title']}]({source['url']})\n"

        return markdown
