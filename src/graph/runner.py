from graph.agent import agentic_ai
from graph.state import AgentState
from db.session import create_db_session, init_db
from db.models import RunRow, AnalysisRow


def run_analysis(dataset_id: str, question: str, dataset_path: str) -> dict:
    """Run the analysis graph and return a result dict for the API."""
    # Create the AnalysisRow with status=pending BEFORE invoking the graph
    with create_db_session() as session:
        row = AnalysisRow(
            dataset_id=dataset_id,
            question=question,
            status="pending",
        )
        session.add(row)
        session.flush()
        analysis_id = row.id

    initial: AgentState = {
        "analysis_id": analysis_id,
        "dataset_id": dataset_id,
        "dataset_path": dataset_path,
        "question": question,
        "error": None,
    }

    final = agentic_ai.invoke(initial)

    return {
        "analysis_id": analysis_id,
        "dataset_id": dataset_id,
        "question": question,
        "answer_text": final.get("answer_text"),
        "chart_json": final.get("chart_json"),
        "status": final.get("status", "completed"),
        "error": final.get("error"),
    }


def run_agent(input_text: str) -> str:
    """Legacy runner kept for backward compatibility with existing tests."""
    init_db()

    with create_db_session() as session:
        run = RunRow(input_text=input_text)
        session.add(run)
        session.flush()
        run_id = run.id

    # Use a minimal state that matches the new graph expectations.
    # The new graph expects dataset_path; without it, ingest_csv will error
    # and handle_error will finalize with status=failed.
    # We create a dummy dataset_path so the legacy tests don't break.
    import tempfile
    import os

    # Write input_text as a tiny CSV so the pipeline can run
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        f.write("input\n")
        f.write(input_text.replace("\n", " ") + "\n")
        tmp_path = f.name

    try:
        # Create a fake dataset_id (no DB row for it — ingest_csv won't fail on missing row)
        import uuid
        fake_dataset_id = str(uuid.uuid4())

        with create_db_session() as session:
            from db.models import AnalysisRow
            row = AnalysisRow(
                dataset_id=fake_dataset_id,
                question=input_text,
                status="pending",
            )
            session.add(row)
            session.flush()
            analysis_id = row.id

        initial: AgentState = {
            "run_id": run_id,
            "analysis_id": analysis_id,
            "dataset_id": fake_dataset_id,
            "dataset_path": tmp_path,
            "question": input_text,
            "error": None,
        }

        final = agentic_ai.invoke(initial)

        with create_db_session() as session:
            run = session.get(RunRow, run_id)
            if run is not None:
                run.status = final.get("status", "completed")
                run.output_text = final.get("answer_text") or final.get("error")
                run.error_message = final.get("error")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return run_id
