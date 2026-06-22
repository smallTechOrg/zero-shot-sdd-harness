class StubGeminiClient:
    def generate_sql(self, prompt: str) -> str:
        return "SELECT * FROM stub_table -- stub-nl-query"
