from agent import Agent

class ReportWriter(Agent):
    def process(self, analysis_text):
        """
        Turn analysis into a readable report.
        """
        self.remember("Writing final report")
        # TODO: use LLM to make a polished summary
        return f"Final Report:\n\n{analysis_text}\n\n-- End of Report --"