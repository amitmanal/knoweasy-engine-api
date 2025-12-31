import re


def _has_any(q: str, words: list[str]) -> bool:
    return any(w in q for w in words)


def try_micro_rule(question: str) -> dict | None:
    """
    Deterministic micro-rules only.
    - Return FULL when unambiguous & safe.
    - Return PARTIAL when key info is missing (workup/substrate/class/temp).
    - Return None when not matched.
    """
    q = (question or "").lower().strip()

    # =========================================================
    # 1) HBr addition to propene (negation-safe)
    # =========================================================
    if ("propene" in q or re.search(r"\bch3\s*-?\s*ch=ch2\b", q) or re.search(r"\bch3ch=ch2\b", q)) and "hbr" in q:
        no_peroxide = bool(re.search(r"(no|without|absence of)\s+peroxide", q))
        q_clean = re.sub(r"(no|without|absence of)\s+peroxide", "", q)

        if _has_any(q_clean, ["peroxide", "roor", "h2o2", "benzoyl peroxide"]):
            return {
                "decision": "FULL",
                "answer": "1-bromopropane (anti-Markovnikov addition due to peroxide effect).",
                "steps": [
                    "Peroxide initiates free-radical chain mechanism.",
                    "Br• adds to terminal carbon (more stable radical).",
                    "Product: 1-bromopropane."
                ],
                "exam_tip": "HBr + peroxide → anti-Markovnikov.",
                "confidence": 0.98,
                "flags": ["MICRO_RULE_HBR_PEROXIDE", "ANTI_MARKOVNIKOV"]
            }

        if no_peroxide or ("peroxide" not in q):
            return {
                "decision": "FULL",
                "answer": "2-bromopropane (Markovnikov addition of HBr to propene).",
                "steps": [
                    "Without peroxide, HBr adds via ionic mechanism.",
                    "More stable carbocation forms at middle carbon.",
                    "Br⁻ attack → 2-bromopropane."
                ],
                "exam_tip": "HBr (no peroxide) → Markovnikov product.",
                "confidence": 0.98,
                "flags": ["MICRO_RULE_HBR_NO_PEROXIDE", "MARKOVNIKOV"]
            }

        return {
            "decision": "PARTIAL",
            "answer": "For HBr addition to alkenes, product depends on whether peroxide is present. Please clarify peroxide present/absent.",
            "steps": [
                "With peroxide → anti-Markovnikov.",
                "Without peroxide → Markovnikov."
            ],
            "exam_tip": "Peroxide effect applies only to HBr.",
            "confidence": 0.55,
            "flags": ["HBR_PEROXIDE_AMBIGUOUS", "NEEDS_INFO"]
        }

    # =========================================================
    # 2) Tollens test
    # =========================================================
    if _has_any(q, ["tollens", "tollen"]) and _has_any(q, ["aldehyde", "cho", "benzaldehyde", "ethanal", "formaldehyde"]):
        return {
            "decision": "FULL",
            "answer": "Silver mirror forms; aldehyde is oxidized to carboxylate/carboxylic acid.",
            "steps": [
                "Tollens’ reagent oxidizes aldehydes.",
                "Ag⁺ reduces to Ag(s) → silver mirror.",
                "Aldehyde converts to carboxylate (acid on acidification)."
            ],
            "exam_tip": "Tollens positive for aldehydes.",
            "confidence": 0.97,
            "flags": ["MICRO_RULE_TOLLENS"]
        }

    # =========================================================
    # 3) Fehling test
    # =========================================================
    if _has_any(q, ["fehling", "fehlings"]) and _has_any(q, ["aldehyde", "ethanal", "acetaldehyde", "aliphatic"]):
        return {
            "decision": "FULL",
            "answer": "Brick-red Cu₂O precipitate forms; aldehyde is oxidized to carboxylate.",
            "steps": [
                "Fehling’s solution contains Cu²⁺ in alkaline medium.",
                "Aliphatic aldehydes reduce Cu²⁺ → Cu₂O.",
                "Brick-red precipitate confirms positive test."
            ],
            "exam_tip": "Fehling positive for aliphatic aldehydes.",
            "confidence": 0.97,
            "flags": ["MICRO_RULE_FEHLING"]
        }

    # =========================================================
    # 4) Iodoform (haloform) test
    # =========================================================
    if _has_any(q, ["iodoform", "haloform"]) or ("i2" in q and "naoh" in q):
        if _has_any(q, ["acetone", "methyl ketone", "ch3coch3", "ch3cor"]):
            return {
                "decision": "FULL",
                "answer": "Yellow precipitate of iodoform (CHI₃) forms; carboxylate is also produced.",
                "steps": [
                    "Methyl ketone undergoes halogenation with I₂/NaOH.",
                    "Cleavage gives yellow CHI₃ precipitate.",
                    "Remaining fragment becomes carboxylate."
                ],
                "exam_tip": "Methyl ketone + I₂/NaOH → iodoform test positive.",
                "confidence": 0.97,
                "flags": ["MICRO_RULE_IODOFORM"]
            }

    # =========================================================
    # 5) KMnO4 oxidation (cold alkaline vs hot acidic)
    # =========================================================
    if "kmno4" in q:
        cold = _has_any(q, ["cold", "dilute", "alkaline", "baeyer"])
        hot = _has_any(q, ["hot", "acidic", "heat", "h+"])

        if cold and not hot:
            return {
                "decision": "FULL",
                "answer": "Cold, dilute alkaline KMnO₄ adds across C=C to give a vicinal diol (glycol).",
                "steps": [
                    "Baeyer test: syn-dihydroxylation of alkene.",
                    "Mild conditions give glycol."
                ],
                "exam_tip": "Cold alkaline KMnO₄ → diol.",
                "confidence": 0.95,
                "flags": ["MICRO_RULE_KMNO4_COLD"]
            }

        if hot:
            return {
                "decision": "FULL",
                "answer": "Hot acidic KMnO₄ causes oxidative cleavage of C=C (products depend on substitution).",
                "steps": [
                    "Strong oxidation under hot acidic conditions.",
                    "Double bond cleaves oxidatively.",
                    "Aldehyde fragments oxidize further."
                ],
                "exam_tip": "Hot acidic KMnO₄ → oxidative cleavage.",
                "confidence": 0.94,
                "flags": ["MICRO_RULE_KMNO4_HOT"]
            }

        return {
            "decision": "PARTIAL",
            "answer": "KMnO₄ outcome depends on conditions: cold alkaline → diol; hot acidic → oxidative cleavage. Please specify conditions.",
            "steps": ["Check temperature and medium (alkaline vs acidic)."],
            "exam_tip": "KMnO₄ is condition-sensitive.",
            "confidence": 0.55,
            "flags": ["KMNO4_CONDITIONS_MISSING", "NEEDS_INFO"]
        }

    # =========================================================
    # 6) Ozonolysis (alkenes): reductive vs oxidative
    # =========================================================
    if "ozon" in q:
        reductive = _has_any(q, ["zn", "zn/h2o", "znh2o", "dms", "(ch3)2s", "dimethyl sulfide", "pph3", "reductive"])
        oxidative = _has_any(q, ["h2o2", "hydrogen peroxide", "oxidative", "h2o2/h2o"])

        substrate = None
        if "propene" in q or re.search(r"\bch3\s*-?\s*ch=ch2\b", q) or re.search(r"\bch3ch=ch2\b", q):
            substrate = "propene"

        if oxidative and not reductive:
            if substrate == "propene":
                return {
                    "decision": "FULL",
                    "answer": "Oxidative ozonolysis of propene gives ethanoic acid (acetic acid) + methanoic acid (formic acid). (Formic acid may further oxidize to CO₂ + H₂O.)",
                    "steps": ["O₃ cleaves C=C; H₂O₂ oxidizes aldehyde fragments to acids."],
                    "exam_tip": "O₃/H₂O₂ → aldehyde fragments become acids.",
                    "confidence": 0.95,
                    "flags": ["MICRO_RULE_OZONOLYSIS_OXIDATIVE", "PROPENE"]
                }

            return {
                "decision": "PARTIAL",
                "answer": "Oxidative ozonolysis (O₃/H₂O₂) cleaves C=C and oxidizes aldehydes to acids. Please specify the alkene to list exact products.",
                "steps": ["Need alkene structure/name for exact cleavage products."],
                "exam_tip": "O₃/H₂O₂ converts aldehydes → acids.",
                "confidence": 0.55,
                "flags": ["MICRO_RULE_OZONOLYSIS_OXIDATIVE_NEEDS_SUBSTRATE", "NEEDS_INFO"]
            }

        if reductive and not oxidative:
            if substrate == "propene":
                return {
                    "decision": "FULL",
                    "answer": "Reductive ozonolysis of propene gives ethanal (acetaldehyde) + methanal (formaldehyde).",
                    "steps": [
                        "O₃ cleaves the C=C bond.",
                        "Reductive workup (Zn/H₂O or DMS) stops at carbonyl stage.",
                        "Propene splits into acetaldehyde + formaldehyde."
                    ],
                    "exam_tip": "O₃ then Zn/H₂O → aldehydes/ketones (no acids).",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_OZONOLYSIS_REDUCTIVE", "PROPENE"]
                }

            return {
                "decision": "FULL",
                "answer": "Reductive ozonolysis (O₃ followed by Zn/H₂O or DMS) cleaves C=C to give aldehydes and/or ketones only.",
                "steps": [
                    "Ozone cleaves the C=C bond.",
                    "Reductive workup prevents further oxidation.",
                    "Final products are aldehydes/ketones."
                ],
                "exam_tip": "O₃ then Zn/H₂O → aldehydes/ketones.",
                "confidence": 0.96,
                "flags": ["MICRO_RULE_OZONOLYSIS_REDUCTIVE_GENERIC"]
            }

        return {
            "decision": "PARTIAL",
            "answer": "Ozonolysis products depend on workup: Zn/H₂O (reductive) → aldehydes/ketones; H₂O₂ (oxidative) → acids. Please specify workup.",
            "steps": ["Look for Zn/H₂O vs H₂O₂ in the question."],
            "exam_tip": "Workup decides product type.",
            "confidence": 0.55,
            "flags": ["MICRO_RULE_OZONOLYSIS_NEEDS_WORKUP", "NEEDS_INFO"]
        }

    # =========================================================
    # 7) Alcohol oxidation: PCC vs K2Cr2O7
    # =========================================================
    if _has_any(q, ["pcc", "k2cr2o7", "dichromate", "jones", "cr2o7"]):
        is_pcc = _has_any(q, ["pcc"])
        is_dichromate = _has_any(q, ["k2cr2o7", "dichromate", "jones", "cr2o7"])

        alcohol_class = None
        if _has_any(q, ["ethanol", "propan-1-ol", "1-propanol", "butan-1-ol", "1-butanol"]):
            alcohol_class = "primary"
        elif _has_any(q, ["propan-2-ol", "2-propanol", "isopropyl alcohol", "isopropanol"]):
            alcohol_class = "secondary"
        elif _has_any(q, ["tert-butanol", "t-butanol", "2-methyl-2-propanol"]):
            alcohol_class = "tertiary"

        if alcohol_class is None:
            return {
                "decision": "PARTIAL",
                "answer": "Alcohol oxidation depends on whether the alcohol is primary, secondary, or tertiary. Please specify the alcohol.",
                "steps": ["Classify alcohol (1°, 2°, 3°) then apply oxidation rule."],
                "exam_tip": "Oxidation outcome depends on alcohol class.",
                "confidence": 0.55,
                "flags": ["ALCOHOL_CLASS_NOT_SPECIFIED", "NEEDS_INFO"]
            }

        if is_pcc:
            if alcohol_class == "primary":
                return {
                    "decision": "FULL",
                    "answer": "Primary alcohol + PCC → aldehyde (stops at aldehyde).",
                    "steps": ["PCC is mild and stops oxidation at aldehyde stage."],
                    "exam_tip": "PCC: 1° → aldehyde; 2° → ketone; 3° → no oxidation.",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_PCC", "PRIMARY_ALCOHOL"]
                }
            if alcohol_class == "secondary":
                return {
                    "decision": "FULL",
                    "answer": "Secondary alcohol + PCC → ketone.",
                    "steps": ["Secondary alcohol oxidizes to ketone; ketone resists further oxidation."],
                    "exam_tip": "2° + PCC → ketone.",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_PCC", "SECONDARY_ALCOHOL"]
                }
            return {
                "decision": "FULL",
                "answer": "Tertiary alcohol does not undergo oxidation with PCC.",
                "steps": ["3° alcohol lacks α-hydrogen needed for oxidation."],
                "exam_tip": "3° alcohols resist oxidation.",
                "confidence": 0.96,
                "flags": ["MICRO_RULE_PCC", "TERTIARY_ALCOHOL", "NO_REACTION"]
            }

        if is_dichromate:
            if alcohol_class == "primary":
                return {
                    "decision": "FULL",
                    "answer": "Primary alcohol + acidified K₂Cr₂O₇ → carboxylic acid.",
                    "steps": ["Strong oxidant: 1° alcohol → aldehyde → carboxylic acid."],
                    "exam_tip": "K₂Cr₂O₇/H⁺: 1° → acid; 2° → ketone; 3° → no oxidation.",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_DICHROMATE", "PRIMARY_ALCOHOL"]
                }
            if alcohol_class == "secondary":
                return {
                    "decision": "FULL",
                    "answer": "Secondary alcohol + acidified K₂Cr₂O₇ → ketone.",
                    "steps": ["2° alcohol oxidizes to ketone; ketone resists further oxidation."],
                    "exam_tip": "2° + K₂Cr₂O₇ → ketone.",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_DICHROMATE", "SECONDARY_ALCOHOL"]
                }
            return {
                "decision": "FULL",
                "answer": "Tertiary alcohol does not undergo oxidation with K₂Cr₂O₇.",
                "steps": ["3° alcohol lacks α-hydrogen needed for oxidation."],
                "exam_tip": "3° alcohols do not oxidize with dichromate.",
                "confidence": 0.96,
                "flags": ["MICRO_RULE_DICHROMATE", "TERTIARY_ALCOHOL", "NO_REACTION"]
            }

    # =========================================================
    # 8) Dehydration of alcohols (conc. H2SO4, temperature-dependent)
    # =========================================================
    dehydration_trigger = (
        _has_any(q, ["dehydration", "dehydrate"])
        or _has_any(q, ["conc h2so4", "concentrated h2so4", "conc. h2so4", "conc h₂so₄"])
        or ("h2so4" in q and _has_any(q, ["heat", "hot", "Δ", "delta"]))
    )

    if dehydration_trigger:
        alcohol = None
        if _has_any(q, ["ethanol"]):
            alcohol = "ethanol"
        elif _has_any(q, ["propan-1-ol", "1-propanol"]):
            alcohol = "propan-1-ol"
        elif _has_any(q, ["propan-2-ol", "2-propanol", "isopropanol", "isopropyl alcohol"]):
            alcohol = "propan-2-ol"
        elif _has_any(q, ["tert-butanol", "t-butanol", "2-methyl-2-propanol"]):
            alcohol = "tert-butanol"

        if alcohol is None:
            return {
                "decision": "PARTIAL",
                "answer": "Dehydration product depends on the alcohol structure (1°, 2°, 3°) and sometimes temperature. Please specify the alcohol.",
                "steps": ["Identify the alcohol, then apply conc. H₂SO₄/heat conditions."],
                "exam_tip": "Alcohol structure decides the alkene formed (often Zaitsev major).",
                "confidence": 0.55,
                "flags": ["DEHYDRATION_NEEDS_ALCOHOL", "NEEDS_INFO"]
            }

        has_140c = _has_any(q, ["140", "413k", "413 k"])
        has_170c = _has_any(q, ["170", "443k", "443 k"])

        if alcohol == "ethanol":
            if has_140c:
                return {
                    "decision": "FULL",
                    "answer": "At ~140°C with conc. H₂SO₄, ethanol forms diethyl ether (intermolecular dehydration).",
                    "steps": ["Lower temperature favors intermolecular dehydration (ether formation)."],
                    "exam_tip": "Ethanol + conc H₂SO₄: 140°C → ether; 170°C → ethene.",
                    "confidence": 0.96,
                    "flags": ["MICRO_RULE_DEHYDRATION_ETHANOL_140C", "ETHER_FORMATION"]
                }
            if has_170c or _has_any(q, ["high temperature", "higher temperature"]):
                return {
                    "decision": "FULL",
                    "answer": "At ~170°C with conc. H₂SO₄, ethanol undergoes dehydration to give ethene.",
                    "steps": ["Higher temperature favors intramolecular dehydration (alkene)."],
                    "exam_tip": "Ethanol + conc H₂SO₄: 170°C → ethene.",
                    "confidence": 0.97,
                    "flags": ["MICRO_RULE_DEHYDRATION_ETHANOL_170C", "ALKENE_FORMATION"]
                }
            return {
                "decision": "PARTIAL",
                "answer": "For ethanol + conc. H₂SO₄, product depends on temperature: 140°C gives diethyl ether; 170°C gives ethene. Please specify temperature.",
                "steps": ["Check whether ~140°C (413 K) or ~170°C (443 K) is given."],
                "exam_tip": "Temperature decides ether vs alkene for ethanol.",
                "confidence": 0.55,
                "flags": ["DEHYDRATION_ETHANOL_NEEDS_TEMP", "NEEDS_INFO"]
            }

        if alcohol in ["propan-1-ol", "propan-2-ol"]:
            return {
                "decision": "FULL",
                "answer": "Dehydration of propanol with conc. H₂SO₄/heat gives propene (alkene formation).",
                "steps": ["Acid + heat causes elimination of water to form alkene."],
                "exam_tip": "Conc. H₂SO₄ + heat → alcohol → alkene.",
                "confidence": 0.96,
                "flags": ["MICRO_RULE_DEHYDRATION_PROPANOL", "ALKENE_FORMATION"]
            }

        if alcohol == "tert-butanol":
            return {
                "decision": "FULL",
                "answer": "Dehydration of tert-butanol with conc. H₂SO₄/heat gives 2-methylpropene (isobutene).",
                "steps": ["Tertiary alcohol dehydrates easily under acidic conditions (E1)."],
                "exam_tip": "3° alcohol + conc. acid/heat → alkene.",
                "confidence": 0.97,
                "flags": ["MICRO_RULE_DEHYDRATION_TERT_BUTANOL", "ALKENE_FORMATION"]
            }

    # =========================================================
    # 9) SN1 / SN2 / E1 / E2 (deterministic routing)
    # =========================================================
    if _has_any(q, ["sn1", "sn2", "e1", "e2", "bromide", "chloride", "iodide", "bromo", "chloro", "iodo", "halide"]):
        substrate = None
        if _has_any(q, ["ethyl bromide", "bromoethane", "1-bromopropane", "n-propyl bromide"]):
            substrate = "primary"
        elif _has_any(q, ["2-bromopropane", "isopropyl bromide", "sec-butyl bromide"]):
            substrate = "secondary"
        elif _has_any(q, ["tert-butyl bromide", "t-butyl bromide"]):
            substrate = "tertiary"

        strong_nuc = _has_any(q, ["cn-", "cyanide", "i-", "br-"])
        strong_base = _has_any(q, ["oh-", "koh", "alcoholic koh", "ethanolic koh", "alc koh", "alc. koh", "alkoxide", "ethoxide", "tert-butoxide", "t-buok"])
        weak_nuc = _has_any(q, ["water", "h2o", "alcohol", "ethanol", "methanol"])
        polar_protic = _has_any(q, ["water", "ethanol", "methanol"])
        polar_aprotic = _has_any(q, ["dmso", "dmf", "acetone"])
        heat = _has_any(q, ["heat", "hot", "Δ", "delta"])

        if substrate is None:
            return {
                "decision": "PARTIAL",
                "answer": "Reaction mechanism depends on substrate class (1°, 2°, 3°). Please specify the substrate.",
                "steps": ["Identify whether the substrate is primary, secondary, or tertiary."],
                "exam_tip": "Substrate class is the first filter for SN/E mechanisms.",
                "confidence": 0.55,
                "flags": ["MECH_NEEDS_SUBSTRATE", "NEEDS_INFO"]
            }

        if substrate == "primary":
            if strong_nuc and polar_aprotic:
                return {
                    "decision": "FULL",
                    "answer": "SN2 mechanism is favored (primary substrate + strong nucleophile + polar aprotic solvent).",
                    "steps": ["Primary carbocation is unstable → no SN1.", "Backside attack → SN2."],
                    "exam_tip": "1° + strong nucleophile + aprotic → SN2.",
                    "confidence": 0.97,
                    "flags": ["MECH_SN2", "PRIMARY"]
                }
            if strong_base and heat:
                return {
                    "decision": "FULL",
                    "answer": "E2 elimination is favored (primary substrate + strong base + heat).",
                    "steps": ["Strong base abstracts β-hydrogen; concerted elimination (E2)."],
                    "exam_tip": "Strong base + heat → E2.",
                    "confidence": 0.96,
                    "flags": ["MECH_E2", "PRIMARY"]
                }
            return {
                "decision": "PARTIAL",
                "answer": "Primary substrates usually undergo SN2 or E2 depending on nucleophile/base and conditions. Please specify nucleophile/base and solvent.",
                "steps": ["Check nucleophile/base strength and solvent."],
                "exam_tip": "Primary: SN2 unless strong base + heat (E2).",
                "confidence": 0.55,
                "flags": ["PRIMARY_MECH_NEEDS_INFO", "NEEDS_INFO"]
            }

        if substrate == "secondary":
            if strong_base and heat:
                return {
                    "decision": "FULL",
                    "answer": "E2 elimination is favored (secondary substrate + strong base + heat).",
                    "steps": ["Strong base abstracts β-hydrogen; concerted E2 elimination."],
                    "exam_tip": "2° + strong base + heat → E2.",
                    "confidence": 0.97,
                    "flags": ["MECH_E2", "SECONDARY"]
                }
            if strong_nuc and polar_aprotic:
                return {
                    "decision": "FULL",
                    "answer": "SN2 substitution is favored (secondary substrate + strong nucleophile + polar aprotic solvent).",
                    "steps": ["Backside attack by strong nucleophile; one-step SN2."],
                    "exam_tip": "2° + strong nucleophile + aprotic → SN2.",
                    "confidence": 0.96,
                    "flags": ["MECH_SN2", "SECONDARY"]
                }
            if weak_nuc and polar_protic:
                if heat:
                    return {
                        "decision": "FULL",
                        "answer": "E1 elimination is favored (secondary substrate + weak nucleophile + polar protic solvent + heat).",
                        "steps": ["Carbocation forms, then elimination gives alkene."],
                        "exam_tip": "Weak nucleophile + heat → E1.",
                        "confidence": 0.95,
                        "flags": ["MECH_E1", "SECONDARY"]
                    }
                return {
                    "decision": "FULL",
                    "answer": "SN1 substitution is favored (secondary substrate + weak nucleophile + polar protic solvent).",
                    "steps": ["Carbocation forms, then nucleophile attacks."],
                    "exam_tip": "2° + weak nucleophile + protic → SN1.",
                    "confidence": 0.95,
                    "flags": ["MECH_SN1", "SECONDARY"]
                }

            return {
                "decision": "PARTIAL",
                "answer": "Secondary substrates can undergo SN1, SN2, or E2 depending on conditions. Please specify nucleophile/base, solvent, and heat.",
                "steps": ["Check nucleophile/base strength, solvent, and temperature."],
                "exam_tip": "2° substrates are condition-sensitive.",
                "confidence": 0.55,
                "flags": ["SECONDARY_MECH_NEEDS_INFO", "NEEDS_INFO"]
            }

        if substrate == "tertiary":
            if strong_base:
                return {
                    "decision": "FULL",
                    "answer": "E2 elimination is favored (tertiary substrate + strong base).",
                    "steps": ["SN2 is blocked by steric hindrance; strong base drives E2."],
                    "exam_tip": "3° + strong base → E2.",
                    "confidence": 0.97,
                    "flags": ["MECH_E2", "TERTIARY"]
                }
            if weak_nuc and polar_protic:
                if heat:
                    return {
                        "decision": "FULL",
                        "answer": "E1 elimination is favored (tertiary substrate + weak nucleophile + heat).",
                        "steps": ["Stable tertiary carbocation forms; elimination gives alkene."],
                        "exam_tip": "3° + weak nucleophile + heat → E1.",
                        "confidence": 0.96,
                        "flags": ["MECH_E1", "TERTIARY"]
                    }
                return {
                    "decision": "FULL",
                    "answer": "SN1 substitution is favored (tertiary substrate + weak nucleophile, no heat).",
                    "steps": ["Stable tertiary carbocation forms; nucleophile attacks."],
                    "exam_tip": "3° + weak nucleophile → SN1.",
                    "confidence": 0.96,
                    "flags": ["MECH_SN1", "TERTIARY"]
                }

            return {
                "decision": "PARTIAL",
                "answer": "Tertiary substrates undergo SN1 or E2 depending on nucleophile/base and heat. Please specify conditions.",
                "steps": ["Check base strength and temperature."],
                "exam_tip": "3° substrates never undergo SN2.",
                "confidence": 0.55,
                "flags": ["TERTIARY_MECH_NEEDS_INFO", "NEEDS_INFO"]
            }

    # =========================================================
    # 10) Aromatic EAS (nitration / halogenation / sulfonation / Friedel–Crafts)
    # =========================================================
    eas_trigger = _has_any(q, ["eas", "electrophilic", "aromatic substitution", "benzene", "nitrobenzene", "toluene", "aniline", "phenol", "chlorobenzene", "benzoic acid"]) or _has_any(q, ["nitration", "br2", "cl2", "fuming", "oleum", "so3", "alcl3", "friedel", "f-c", "f.c."])

    if eas_trigger:
                # ---- identify ring substrate (robust: word-boundary matching) ----
        ring = None

        def _has_word(term: str) -> bool:
            return re.search(rf"\b{re.escape(term)}\b", q) is not None

        if _has_word("nitrobenzene"):
            ring = "nitrobenzene"
        elif _has_word("benzoic acid"):
            ring = "benzoic_acid"
        elif _has_word("chlorobenzene"):
            ring = "chlorobenzene"
        elif _has_word("toluene"):
            ring = "toluene"
        elif _has_word("phenol"):
            ring = "phenol"
        elif _has_word("aniline"):
            ring = "aniline"
        elif _has_word("benzene"):
            ring = "benzene"



        # ---- detect reaction type ----
        nitration = ("nitration" in q) or ("hno3" in q and "h2so4" in q) or _has_any(q, ["mixed acid", "conc hno3", "conc h2so4"])
        bromination = ("br2" in q) and _has_any(q, ["febr3", "fe/br3", "fe br3"])
        chlorination = ("cl2" in q) and _has_any(q, ["fecl3", "fe/cl3", "fe cl3"])
        sulfonation = _has_any(q, ["so3", "oleum", "fuming h2so4", "fuming sulfuric", "benzenesulfonic", "sulphonation", "sulfonation"])
        fc_alkyl = _has_any(q, ["friedel", "f-c", "f.c."]) and ("alcl3" in q) and _has_any(q, ["ch3cl", "alkyl chloride", "rcl"])
        fc_acyl = _has_any(q, ["friedel", "f-c", "f.c."]) and ("alcl3" in q) and _has_any(q, ["ch3cocl", "acyl chloride", "rco cl", "rco cl", "rco cl"])

        # If EAS asked but reaction type unclear → PARTIAL
        if not any([nitration, bromination, chlorination, sulfonation, fc_alkyl, fc_acyl]):
            return {
                "decision": "PARTIAL",
                "answer": "Aromatic EAS product depends on the electrophile and conditions (e.g., nitration, halogenation, sulfonation, Friedel–Crafts). Please specify reagents/conditions.",
                "steps": ["Identify the EAS type from reagents."],
                "exam_tip": "Always map reagents → electrophile first.",
                "confidence": 0.55,
                "flags": ["EAS_NEEDS_REAGENTS", "NEEDS_INFO"]
            }

        # If reaction type clear but ring unknown → PARTIAL
        if ring is None:
            return {
                "decision": "PARTIAL",
                "answer": "EAS orientation depends on the aromatic substrate (benzene vs substituted benzene). Please specify the substrate.",
                "steps": ["Name the aromatic ring (benzene/toluene/nitrobenzene/etc.)."],
                "exam_tip": "Directing effects control o/p vs meta.",
                "confidence": 0.55,
                "flags": ["EAS_NEEDS_SUBSTRATE", "NEEDS_INFO"]
            }

        # Directing groups
        op_director = ring in ["toluene", "phenol", "aniline", "chlorobenzene"]
        meta_director = ring in ["nitrobenzene", "benzoic_acid"]

        # ---- NITRATION outputs ----
        if nitration:
            if ring == "benzene":
                return {
                    "decision": "FULL",
                    "answer": "Nitration of benzene (conc HNO₃/H₂SO₄) gives nitrobenzene.",
                    "steps": ["Electrophile: NO₂⁺ (nitronium ion).", "Substitution gives nitrobenzene."],
                    "exam_tip": "Benzene + mixed acid → nitrobenzene.",
                    "confidence": 0.97,
                    "flags": ["EAS_NITRATION", "BENZENE"]
                }
            if op_director:
                return {
                    "decision": "FULL",
                    "answer": f"Nitration gives ortho- and para-substituted products (para major) for {ring}.",
                    "steps": ["Activating (or halogen) group directs o/p.", "Para is often major due to less steric hindrance."],
                    "exam_tip": "o/p directors → o- and p- products (p major).",
                    "confidence": 0.95,
                    "flags": ["EAS_NITRATION", "ORTHO_PARA_DIRECTING"]
                }
            if meta_director:
                return {
                    "decision": "FULL",
                    "answer": f"Nitration gives meta-substituted product for {ring} (meta directing).",
                    "steps": ["Strongly deactivating group directs meta."],
                    "exam_tip": "NO₂, COOH → meta directing.",
                    "confidence": 0.95,
                    "flags": ["EAS_NITRATION", "META_DIRECTING"]
                }

        # ---- HALOGENATION outputs ----
        if bromination or chlorination:
            hal = "bromo" if bromination else "chloro"
            if ring == "benzene":
                return {
                    "decision": "FULL",
                    "answer": f"{hal.capitalize()}nation of benzene gives {hal}benzene.",
                    "steps": ["Lewis acid catalyst generates electrophile.", "Substitution gives halobenzene."],
                    "exam_tip": "Br₂/FeBr₃ → bromobenzene; Cl₂/FeCl₃ → chlorobenzene.",
                    "confidence": 0.97,
                    "flags": ["EAS_HALOGENATION", "BENZENE"]
                }
            if op_director:
                return {
                    "decision": "FULL",
                    "answer": f"{hal.capitalize()}nation gives ortho- and para-products (para major) for {ring}.",
                    "steps": ["o/p directing group directs substitution to o and p positions."],
                    "exam_tip": "o/p directors → o- and p- products.",
                    "confidence": 0.95,
                    "flags": ["EAS_HALOGENATION", "ORTHO_PARA_DIRECTING"]
                }
            if meta_director:
                return {
                    "decision": "FULL",
                    "answer": f"{hal.capitalize()}nation gives meta-product for {ring} (meta directing).",
                    "steps": ["Meta directing group guides substitution to meta position."],
                    "exam_tip": "NO₂, COOH → meta directing.",
                    "confidence": 0.95,
                    "flags": ["EAS_HALOGENATION", "META_DIRECTING"]
                }

        # ---- SULFONATION outputs ----
        if sulfonation:
            if ring == "benzene":
                return {
                    "decision": "FULL",
                    "answer": "Sulfonation of benzene (SO₃/oleum) gives benzenesulfonic acid.",
                    "steps": ["Electrophile: SO₃ or protonated SO₃.", "Substitution gives sulfonic acid."],
                    "exam_tip": "SO₃/oleum → benzenesulfonic acid.",
                    "confidence": 0.96,
                    "flags": ["EAS_SULFONATION", "BENZENE"]
                }
            if op_director:
                return {
                    "decision": "FULL",
                    "answer": f"Sulfonation gives ortho- and para-products (para major) for {ring}.",
                    "steps": ["o/p directing group → o and p substitution."],
                    "exam_tip": "o/p directors → o- and p- products.",
                    "confidence": 0.94,
                    "flags": ["EAS_SULFONATION", "ORTHO_PARA_DIRECTING"]
                }
            if meta_director:
                return {
                    "decision": "FULL",
                    "answer": f"Sulfonation gives meta-product for {ring} (meta directing).",
                    "steps": ["Meta directing group guides substitution."],
                    "exam_tip": "NO₂, COOH → meta directing.",
                    "confidence": 0.94,
                    "flags": ["EAS_SULFONATION", "META_DIRECTING"]
                }

        # ---- Friedel–Crafts outputs (ultra safe) ----
        if fc_alkyl or fc_acyl:
            if ring != "benzene":
                # Keep ultra-safe: do not attempt substituted rings for FC yet
                return {
                    "decision": "PARTIAL",
                    "answer": "Friedel–Crafts on substituted rings depends on activation/deactivation and rearrangements. Please specify if the ring is plain benzene or share full details.",
                    "steps": ["For now, engine gives FULL only for benzene + simple FC reagents."],
                    "exam_tip": "Strongly deactivated rings do not undergo Friedel–Crafts.",
                    "confidence": 0.55,
                    "flags": ["FC_NEEDS_SAFE_SCOPE", "NEEDS_INFO"]
                }

            if fc_alkyl:
                return {
                    "decision": "FULL",
                    "answer": "Friedel–Crafts alkylation of benzene with CH₃Cl/AlCl₃ gives toluene.",
                    "steps": ["Electrophile forms with AlCl₃.", "Benzene substitutes → toluene."],
                    "exam_tip": "CH₃Cl/AlCl₃ + benzene → toluene.",
                    "confidence": 0.95,
                    "flags": ["FC_ALKYLATION", "BENZENE"]
                }

            if fc_acyl:
                return {
                    "decision": "FULL",
                    "answer": "Friedel–Crafts acylation of benzene with CH₃COCl/AlCl₃ gives acetophenone.",
                    "steps": ["Acylium ion forms.", "Benzene substitutes → acylbenzene (acetophenone)."],
                    "exam_tip": "CH₃COCl/AlCl₃ + benzene → acetophenone.",
                    "confidence": 0.95,
                    "flags": ["FC_ACYLATION", "BENZENE"]
                }

    return None
