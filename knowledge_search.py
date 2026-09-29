from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from drive_kb import load_folder
from config import DRIVE_FOLDER_ID


CHUNK_SIZE = 1200
MIN_SCORE = 0.08


def split_into_chunks(text, chunk_size=CHUNK_SIZE):
    text = text.strip()

    if not text:
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in text.split("\n")
        if paragraph.strip()
    ]

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:

        if len(current_chunk) + len(paragraph) <= chunk_size:

            if current_chunk:
                current_chunk += "\n"

            current_chunk += paragraph

        else:

            if current_chunk:
                chunks.append(current_chunk)

            current_chunk = paragraph

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def get_source_tier(name, folder_path):
    """
    Чем меньше tier, тем выше приоритет источника.

    0 = Knowledge Base / основной документ
    1 = Гайды
    2 = Чек-листы
    3 = Шаблоны / сравнения
    4 = Остальные материалы
    5 = Telegram notes
    """

    name_lower = name.lower()
    path_lower = folder_path.lower()

    # Главные Knowledge Base
    if (
        "knowledge base" in name_lower
        or "base knowledge" in name_lower
        or "база знаний" in name_lower
        or "основной документ" in name_lower
    ):
        return 0

    # Полноценные гайды
    if "гайды" in path_lower:
        return 1

    # Чек-листы
    if "чек-листы" in path_lower:
        return 2

    # Шаблоны и сравнительные материалы
    if (
        "шаблоны" in path_lower
        or "сравнен" in name_lower
    ):
        return 3

    # Telegram notes — только последний fallback
    if (
        "телеграм" in path_lower
        or "telegram" in path_lower
        or "заметки" in path_lower
    ):
        return 5

    return 4


def build_knowledge_base():
    documents = load_folder(DRIVE_FOLDER_ID)

    chunks = []

    for document in documents:

        text = document["text"].strip()

        if not text:
            continue

        document_chunks = split_into_chunks(text)

        for chunk in document_chunks:

            chunks.append(
                {
                    "text": chunk,
                    "name": document["name"],
                    "url": document["url"],
                    "folder_path": document["folder_path"],
                    "tier": get_source_tier(
                        document["name"],
                        document["folder_path"],
                    ),
                }
            )

    return chunks


def search_knowledge_base(question, chunks, top_k=3):

    if not chunks:
        return []

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    titles = [
        chunk["name"]
        for chunk in chunks
    ]

    paths = [
        chunk["folder_path"]
        for chunk in chunks
    ]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        lowercase=True,
    )

    matrix = vectorizer.fit_transform(
        texts
        + titles
        + paths
        + [question]
    )

    count = len(chunks)

    text_vectors = matrix[:count]

    title_vectors = matrix[
        count:count * 2
    ]

    path_vectors = matrix[
        count * 2:count * 3
    ]

    question_vector = matrix[-1]

    text_scores = cosine_similarity(
        question_vector,
        text_vectors,
    )[0]

    title_scores = cosine_similarity(
        question_vector,
        title_vectors,
    )[0]

    path_scores = cosine_similarity(
        question_vector,
        path_vectors,
    )[0]

    candidates = []

    for index, chunk in enumerate(chunks):

        relevance = (
            text_scores[index] * 0.70
            + title_scores[index] * 0.25
            + path_scores[index] * 0.05
        )

        if relevance < MIN_SCORE:
            continue

        candidate = chunk.copy()
        candidate["score"] = float(relevance)

        candidates.append(candidate)

    # Сначала сортируем по типу источника:
    # KB -> guide -> checklist -> template -> other -> Telegram
    #
    # Внутри одного типа — по релевантности.
    candidates.sort(
        key=lambda item: (
            item["tier"],
            -item["score"],
        )
    )

    results = []
    seen_sources = set()

    for candidate in candidates:

        if candidate["name"] in seen_sources:
            continue

        seen_sources.add(
            candidate["name"]
        )

        results.append(candidate)

        if len(results) >= top_k:
            break

    return results


def tier_name(tier):
    names = {
        0: "Knowledge Base",
        1: "Гайд",
        2: "Чек-лист",
        3: "Шаблон / сравнение",
        4: "Дополнительный материал",
        5: "Telegram notes",
    }

    return names.get(
        tier,
        "Материал",
    )


if __name__ == "__main__":

    print(
        "Загружаю Knowledge Base...\n"
    )

    chunks = build_knowledge_base()

    print(
        f"\nKnowledge Base готова. "
        f"Фрагментов: {len(chunks)}"
    )

    while True:

        question = input(
            "\nВведите вопрос или 'exit': "
        ).strip()

        if question.lower() == "exit":
            break

        results = search_knowledge_base(
            question,
            chunks,
        )

        if not results:

            print(
                "\nНе найдено достаточно информации "
                "в материалах BilimBiz."
            )

            continue

        print("\nНайдено:\n")

        for number, result in enumerate(
            results,
            start=1,
        ):

            print(
                f"--- Результат {number} ---"
            )

            print(
                f"Источник: {result['name']}"
            )

            print(
                f"Тип: {tier_name(result['tier'])}"
            )

            print(
                f"Папка: "
                f"{result['folder_path']}"
            )

            print(
                f"Совпадение: "
                f"{result['score']:.3f}"
            )

            print()

            print(
                result["text"][:800]
            )

            if result["url"]:

                print(
                    f"\nСсылка: "
                    f"{result['url']}"
                )

            print()