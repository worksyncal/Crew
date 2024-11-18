from typing import List

from crewai.knowledge.embedder.base_embedder import BaseEmbedder
from crewai.knowledge.source.base_file_knowledge_source import BaseFileKnowledgeSource


class TextFileKnowledgeSource(BaseFileKnowledgeSource):
    """A knowledge source that stores and queries text file content using embeddings."""

    def load_content(self) -> str:
        """Load and preprocess text file content."""
        super().load_content()  # Validate the file path
        with self.file_path.open("r", encoding="utf-8") as f:
            return f.read()

    def add(self) -> None:
        """
        Add text file content to the knowledge source, chunk it, compute embeddings,
        and save the embeddings.
        """
        new_chunks = self._chunk_text(self.content)
        self.chunks.extend(new_chunks)
        self.save_documents(metadata=self.metadata)

    def _chunk_text(self, text: str) -> List[str]:
        """Utility method to split text into chunks."""
        return [
            text[i : i + self.chunk_size]
            for i in range(0, len(text), self.chunk_size - self.chunk_overlap)
        ]
