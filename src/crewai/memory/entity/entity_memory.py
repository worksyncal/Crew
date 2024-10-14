from crewai.memory.entity.entity_memory_item import EntityMemoryItem
from crewai.memory.memory import Memory
from crewai.memory.storage.rag_storage import RAGStorage
from crewai.memory.storage.mem0_storage import Mem0Storage


class EntityMemory(Memory):
    """
    EntityMemory class for managing structured information about entities
    and their relationships using SQLite storage.
    Inherits from the Memory class.
    """

    def __init__(self, crew=None, embedder_config=None, storage=None):
        self.memory_provider = crew.memory_config["provider"]
        if self.memory_provider == "mem0":
            storage = Mem0Storage(
                type="entities",
                crew=crew,
            )
        else:
            storage = (
                storage
                if storage
                else RAGStorage(
                    type="entities",
                    allow_reset=False,
                    embedder_config=embedder_config,
                    crew=crew,
                )
            )
        super().__init__(storage)

    def save(self, item: EntityMemoryItem) -> None:  # type: ignore # BUG?: Signature of "save" incompatible with supertype "Memory"
        """Saves an entity item into the SQLite storage."""
        if self.memory_provider == "mem0":
            data = f"""
            Remember details about the following entity:
            Name: {item.name}
            Type: {item.type}
            Entity Description: {item.description}
            """
        else:
            data = f"{item.name}({item.type}): {item.description}"
        super().save(data, item.metadata)

    def reset(self) -> None:
        try:
            self.storage.reset()
        except Exception as e:
            raise Exception(f"An error occurred while resetting the entity memory: {e}")
