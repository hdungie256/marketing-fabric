class UnknownTermError(LookupError):
    def __init__(self, term_id: str):
        super().__init__(f"Unknown glossary term: {term_id}")
        self.term_id = term_id


class NotPermittedError(PermissionError):
    def __init__(self, dataset_id: str):
        super().__init__(f"Not permitted for role: {dataset_id}")
        self.dataset_id = dataset_id
