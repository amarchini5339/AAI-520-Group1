from agent import Agent

class FinancialAnalyst(Agent):
    def process(self, research_outputs):
        """
        Combine research from multiple sources and analyze.
        """
        self.remember("Analyzing research outputs")
        # TODO: add financial analysis logic here
        combined = "\n".join([f"{r['source']}: {r['data']}" for r in research_outputs])
        return f"Analysis Report:\n{combined}"