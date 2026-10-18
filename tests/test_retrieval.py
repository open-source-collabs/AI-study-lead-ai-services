from app.schemas.document import ExtractedPage
from app.services.document_service import chunk_pages
from app.services.retrieval import select_chunks


def make_chunks():
    pages = [
        ExtractedPage(page_number=1, text="Photosynthesis happens in the chloroplast and uses sunlight."),
        ExtractedPage(page_number=2, text="Quick sort partitions an array around a pivot element."),
        ExtractedPage(page_number=3, text="The French Revolution began in 1789 in Paris."),
    ]
    return chunk_pages(pages, 500, 0)


def test_best_matching_chunk_is_found():
    picked = select_chunks(make_chunks(), "How does quick sort choose a pivot?", top_k=1)
    assert [chunk.start_page for chunk in picked] == [2]


def test_results_come_back_in_document_order():
    picked = select_chunks(make_chunks(), "pivot chloroplast", top_k=2)
    assert [chunk.start_page for chunk in picked] == [1, 2]


def test_no_overlap_means_no_results():
    assert select_chunks(make_chunks(), "quantum entanglement", top_k=3) == []


def test_empty_inputs_are_safe():
    assert select_chunks([], "anything", top_k=3) == []
    assert select_chunks(make_chunks(), "   ", top_k=3) == []
