from app.normalize import normalized_header, safe_text


def test_header_normalization_and_formula_protection():
    assert normalized_header(" Matrícula ") == "matricula"
    assert safe_text("=1+1") == "'=1+1"
