import base64
import io
import zipfile

from fastapi.testclient import TestClient

from app.dashboard.app import app


def test_e2e_api_flow_create_pipeline_approve_wait_merge_and_done(db_session, tmp_path, monkeypatch):
    """Сквозной API flow: create -> pipeline -> attach PR -> approve -> merged."""
    from app.orchestrator import court as court_module
    from app.orchestrator import pipeline as pipeline_module

    monkeypatch.setattr(court_module, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}

    create_resp = client.post(
        "/api/tasks",
        json={"owner_text": "# TASK deploy prod after smoke and rollback check"},
        headers=headers,
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    pipeline_resp = client.post(f"/api/tasks/{task_id}/pipeline/run", headers=headers)
    assert pipeline_resp.status_code == 200
    assert pipeline_resp.json()["status"] == "WAIT_OWNER"

    documents_resp = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    assert documents_resp.status_code == 200
    documents = documents_resp.json()["documents"]
    assert [item["kind"] for item in documents[:2]] == ["verdict", "report"]

    verdict_resp = client.get(f"/api/tasks/{task_id}/documents/verdict", headers=headers)
    assert verdict_resp.status_code == 200
    assert "каноничное финальное решение команды после суда" in verdict_resp.json()["content"].lower()

    patch_resp = client.patch(
        f"/api/tasks/{task_id}",
        json={"pr_url": "https://github.com/example/repo/pull/1"},
        headers=headers,
    )
    assert patch_resp.status_code == 200

    approve_resp = client.post(f"/api/tasks/{task_id}/approve", headers=headers)
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "APPROVED_WAIT_MERGE"

    docs_after_approve = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    assert docs_after_approve.status_code == 200
    approve_titles = [item["title"] for item in docs_after_approve.json()["documents"]]
    assert "Решение владельца" in approve_titles

    merged_resp = client.post(f"/api/tasks/{task_id}/merged", headers=headers)
    assert merged_resp.status_code == 200
    assert merged_resp.json()["status"] == "DONE"

    task_resp = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert task_resp.status_code == 200
    assert task_resp.json()["status"] == "DONE"
    assert task_resp.json()["verdict_path"].endswith("final_verdict.md")

    docs_after_merge = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    assert docs_after_merge.status_code == 200
    merge_titles = [item["title"] for item in docs_after_merge.json()["documents"]]
    assert "Подтверждение merge" in merge_titles


def test_e2e_api_flow_uploads_txt_and_docx_as_task_documents(db_session, tmp_path, monkeypatch):
    from app.dashboard import api_router as api_router_module
    from app.orchestrator import pipeline as pipeline_module

    monkeypatch.setattr(api_router_module, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-API-Key": "test_key_for_smoke"}

    create_resp = client.post(
        "/api/tasks",
        json={"owner_text": "# TASK Использовать вложенные файлы как контекст миссии"},
        headers=headers,
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["id"]

    txt_payload = base64.b64encode("Краткое техническое описание для команды.".encode("utf-8")).decode("ascii")
    docx_payload = base64.b64encode(_build_test_docx("Русский текст из DOCX для команды.")).decode("ascii")

    upload_resp = client.post(
        f"/api/tasks/{task_id}/attachments/upload",
        json={
            "files": [
                {"name": "brief.txt", "content_base64": txt_payload},
                {"name": "spec.docx", "content_base64": docx_payload},
            ]
        },
        headers=headers,
    )
    assert upload_resp.status_code == 200
    uploaded = upload_resp.json()["uploaded"]
    assert [item["name"] for item in uploaded] == ["brief.txt", "spec.docx"]

    documents_resp = client.get(f"/api/tasks/{task_id}/documents", headers=headers)
    assert documents_resp.status_code == 200
    documents = documents_resp.json()["documents"]
    attachment_docs = [item for item in documents if item["kind"] == "attachment"]
    assert [item["title"] for item in attachment_docs] == ["brief.txt", "spec.docx"]

    txt_doc = attachment_docs[0]
    txt_read_resp = client.get(f"/api/tasks/{task_id}/documents/{txt_doc['key']}", headers=headers)
    assert txt_read_resp.status_code == 200
    assert "Краткое техническое описание" in txt_read_resp.json()["content"]

    docx_doc = attachment_docs[1]
    docx_read_resp = client.get(f"/api/tasks/{task_id}/documents/{docx_doc['key']}", headers=headers)
    assert docx_read_resp.status_code == 200
    assert "Русский текст из DOCX" in docx_read_resp.json()["content"]

    download_resp = client.get(f"/tasks/{task_id}/documents/{docx_doc['key']}/download", headers=headers)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    task_resp = client.get(f"/api/tasks/{task_id}", headers=headers)
    assert task_resp.status_code == 200
    assert any("brief.txt" in item["path"] for item in task_resp.json()["documents"] if item["kind"] == "attachment")


def _build_test_docx(text: str) -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()
