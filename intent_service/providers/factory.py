from ..config import settings
from ..utils.exceptions import UnsupportedClassifierError
from .base_classifier import BaseIntentClassifier
from .keyword_classifier import KeywordIntentClassifier, taxonomy_for_language


def create_classifier(classifier_name: str | None = None) -> BaseIntentClassifier:
    normalized_name = (classifier_name or settings.classifier_name or "keyword").lower()
    classifiers: dict[str, type[BaseIntentClassifier]] = {
        "keyword": KeywordIntentClassifier,
    }
    classifier_cls = classifiers.get(normalized_name)
    if classifier_cls is None:
        raise UnsupportedClassifierError(
            f"Unsupported classifier '{classifier_name or settings.classifier_name}'"
        )
    return classifier_cls()


def create_classifier_for_language(language: str) -> BaseIntentClassifier | None:
    """Phase C3: returns a KeywordIntentClassifier loaded with `language`'s
    taxonomy (see providers/keyword_classifier.py's LANGUAGE_TAXONOMY_FILES),
    or None if no taxonomy is registered for that language yet - callers
    (api/dependencies.py's classifier_factory, IntentService) treat None as
    "this language isn't supported" and report `language_supported=False`
    rather than guessing with the wrong-language taxonomy.

    Only the keyword engine is localized today - if `INTENT_CLASSIFIER` is
    ever set to a different engine in the future, this function will need a
    matching per-engine branch, same as `create_classifier` above.
    """

    taxonomy = taxonomy_for_language(language)
    if taxonomy is None:
        return None
    return KeywordIntentClassifier(taxonomy=taxonomy)
