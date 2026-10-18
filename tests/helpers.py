import json

from app.services.providers import Provider


class FakeProvider(Provider):
    def __init__(self, replies, name="fake", model="fake-model"):
        super().__init__(name, model)
        self.replies = list(replies)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return reply if isinstance(reply, str) else json.dumps(reply)


def make_pdf(page_texts: list[str]) -> bytes:
    # an empty string makes a blank page
    count = len(page_texts)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(count))
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for i, text in enumerate(page_texts):
        page_id, content_id = 4 + 2 * i, 5 + 2 * i
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode() if text else b""
        objects[content_id] = b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for number in sorted(objects):
        out += f"{offsets[number]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def doc(*texts: str, title: str = "Lecture") -> dict:
    return {"title": title, "pages": [{"page_number": i, "text": t} for i, t in enumerate(texts, start=1)]}
