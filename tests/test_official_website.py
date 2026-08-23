from app.official_website import parse_official_html


def test_official_html_parser_extracts_ids_dates_answers_and_images() -> None:
    html = """
    <h3 class="subH3">Topic name</h3>
    <ol class="patnact">
      <li>
        <div class="results"><span class="correct" id="c_123"></span></div>
        <div class="text">What is correct?</div>
        <div class="q_pic"><img src="/prompt.jpg"></div>
        <ol class="alternatives">
          <li><label><input type="radio" name="r_123"> A) First.</label></li>
          <li><label><input type="radio" name="r_123"> B) Second.</label></li>
          <li><label><input type="radio" name="r_123"> C) Third.</label></li>
          <li><label><input type="radio" name="r_123"> D) Fourth.</label></li>
          <li class="spravnaOdpoved"><span class="spravne">Správná odpověď: B</span></li>
          <li class="datumAktualizace">Datum aktualizace testové úlohy: 5. 1. 2026</li>
        </ol>
      </li>
    </ol>
    """.encode()
    bank, images = parse_official_html(html, "https://example.test/bank/")
    question = bank.questions[0]
    assert question.stable_key == "1.1"
    assert question.official_id == "123"
    assert question.source_updated_on.isoformat() == "2026-01-05"
    assert question.correct_answer == "B"
    assert images["1-1-prompt.jpg"] == "https://example.test/prompt.jpg"
