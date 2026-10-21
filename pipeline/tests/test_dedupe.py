from datetime import date, timedelta

from veille_pipeline.dedupe import Candidate, find_duplicates

D = date(2026, 10, 21)


def c(id, title, org, seen=D):
    return Candidate(id, title, org, seen)


def test_same_offer_on_three_sources():
    # titres réels ReliefWeb ; variantes de ponctuation, casse et accents vues entre sources
    offers = [
        c(1, "Monitoring, Evaluation and Learning Specialist", "Habitat for Humanity"),
        c(2, "Monitoring Evaluation and Learning Specialist", "Habitat for Humanity International"),
        c(3, "MONITORING, EVALUATION AND LEARNING SPECIALIST", "habitat for humanity"),
    ]
    assert find_duplicates(offers) == {2: 1, 3: 1}


def test_slash_variant_from_reliefweb():
    offers = [c(79, "Software Developer Analyst", "International Rescue Committee"),
              c(98, "Software Developer / Analyst", "International Rescue Committee")]
    assert find_duplicates(offers) == {98: 79}


def test_translated_titles_not_merged():
    offers = [c(1, "Chargé de projet eau et assainissement", "Fondation Mérieux"),
              c(2, "Water and sanitation project officer", "Fondation Mérieux")]
    assert find_duplicates(offers) == {}


def test_same_org_different_location_not_merged():
    # deux postes réels d'IMPACT Initiatives : le score titre + organisation atteindrait 90,3
    offers = [c(41, "Senior Research Officer - MSNA - Global, Based in Amman", "IMPACT Initiatives"),
              c(66, "Senior Research Officer – MSNA – Global, based in Dakar", "IMPACT Initiatives")]
    assert find_duplicates(offers) == {}


def test_baseline_and_endline_not_merged():
    offers = [c(43, "External Baseline Evaluation Consultancy for Water and Education", "Islamic Relief Kenya"),
              c(38, "External Endline Evaluation Consultancy for Promoting Access to Water", "Islamic Relief Kenya")]
    assert find_duplicates(offers) == {}


def test_different_org_not_merged():
    offers = [c(1, "Monitoring and Evaluation Advisor", "All Hands and Hearts"),
              c(2, "Monitoring and Evaluation Advisor", "Danish Refugee Council")]
    assert find_duplicates(offers) == {}


def test_missing_organization_not_merged_approximately():
    offers = [c(1, "Research Analyst", None), c(2, "Research analyst.", "Laterite")]
    assert find_duplicates(offers) == {}


def test_window_of_60_days():
    old = D - timedelta(days=61)
    offers = [c(1, "Research Analyst", "Laterite", old), c(2, "Research Analyst.", "Laterite", D)]
    assert find_duplicates(offers) == {}
    assert find_duplicates([c(1, "Research Analyst", "Laterite", D - timedelta(days=60)),
                            c(2, "Research Analyst.", "Laterite", D)]) == {2: 1}
