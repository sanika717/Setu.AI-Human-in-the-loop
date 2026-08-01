class DocumentValidationError(Exception):
    """Base exception for document validation engine failures."""


class UnsupportedDocumentTypeError(DocumentValidationError):
    """Raised when a document type is not part of the supported catalog."""


class MetadataValidationError(DocumentValidationError):
    """Raised when document metadata (mime type, size, pages) fails validation."""


class OCRValidationError(DocumentValidationError):
    """Raised when OCR-extracted text fails quality validation."""


class UnknownServiceError(DocumentValidationError):
    """Raised when an unrecognized service_id is supplied for pre-validation."""
