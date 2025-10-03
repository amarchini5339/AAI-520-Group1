from agent import Agent

class Coordinator(Agent):
    def __init__(self, name, researchers, analyst, writer):
        super().__init__(name)
        self.researchers = researchers
        self.analyst = analyst
        self.writer = writer

    def process(self, symbol):
        """
        Routing logic: decide which researchers to query.
        """
        self.remember(f"Coordinating research for {symbol}")

        research_results = []
        for researcher in self.researchers:
            result = researcher.process(symbol)
            research_results.append(result)

        analysis = self.analyst.process(research_results)
        report = self.writer.process(analysis)

        return report