"""QTI parse/serialize round-trip and SCORM manifest parse."""

from __future__ import annotations

from app import QTIInteraction, Standard
from app.adapters import QTIAdapter, QTIParseError, SCORMAdapter, SCORMParseError


QTI_CHOICE = """<?xml version="1.0"?>
<assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v2p2"
    identifier="q-photosynthesis" title="Photosynthesis" adaptive="false">
  <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="identifier">
    <correctResponse><value>B</value></correctResponse>
  </responseDeclaration>
  <itemBody>
    <choiceInteraction responseIdentifier="RESPONSE" maxChoices="1">
      <prompt>Where does photosynthesis occur?</prompt>
      <simpleChoice identifier="A">Mitochondria</simpleChoice>
      <simpleChoice identifier="B">Chloroplast</simpleChoice>
      <simpleChoice identifier="C">Nucleus</simpleChoice>
    </choiceInteraction>
  </itemBody>
</assessmentItem>
"""


def test_qti_parse_choice_item_with_answer_key():
    adapter = QTIAdapter("qti:test")
    item = adapter.parse_item(QTI_CHOICE)
    assert item.identifier == "q-photosynthesis"
    assert item.interaction is QTIInteraction.CHOICE
    assert item.prompt == "Where does photosynthesis occur?"
    assert len(item.choices) == 3
    assert item.correct_responses == ["B"]
    assert item.has_answer_key is True
    correct = [c for c in item.choices if c.correct]
    assert len(correct) == 1 and correct[0].identifier == "B"


def test_qti_roundtrip_serialize_then_parse():
    adapter = QTIAdapter("qti:test")
    item = adapter.parse_item(QTI_CHOICE)
    xml = adapter.serialize_item(item)
    reparsed = adapter.parse_item(xml)
    assert reparsed.identifier == item.identifier
    assert reparsed.interaction is QTIInteraction.CHOICE
    assert reparsed.correct_responses == ["B"]
    assert [c.identifier for c in reparsed.choices] == ["A", "B", "C"]


def test_qti_parse_text_entry():
    xml = """<?xml version="1.0"?>
    <assessmentItem xmlns="http://www.imsglobal.org/xsd/imsqti_v3p0"
        identifier="q2" title="Capital">
      <responseDeclaration identifier="RESPONSE" cardinality="single" baseType="string">
        <correctResponse><value>Paris</value></correctResponse>
      </responseDeclaration>
      <itemBody>
        <p>What is the capital of France?</p>
        <textEntryInteraction responseIdentifier="RESPONSE"/>
      </itemBody>
    </assessmentItem>
    """
    item = QTIAdapter("qti:test").parse_item(xml)
    assert item.interaction is QTIInteraction.TEXT_ENTRY
    assert item.correct_responses == ["Paris"]


def test_qti_empty_raises():
    raised = False
    try:
        QTIAdapter("qti:test").parse_item("")
    except QTIParseError:
        raised = True
    assert raised


def test_qti_malformed_raises():
    raised = False
    try:
        QTIAdapter("qti:test").parse_item("<assessmentItem><itemBody>")
    except QTIParseError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# SCORM
# ---------------------------------------------------------------------------
SCORM_12 = """<?xml version="1.0"?>
<manifest identifier="PKG-1" version="1.0"
    xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
    xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
  <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>Intro to Fractions</title>
      <item identifier="ITEM-1" identifierref="RES-1"><title>Lesson 1</title></item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-1" type="webcontent" adlcp:scormtype="sco" href="lesson1.html"/>
    <resource identifier="RES-2" type="webcontent" adlcp:scormtype="asset" href="style.css"/>
  </resources>
</manifest>
"""


def test_scorm_parse_manifest_12():
    adapter = SCORMAdapter("scorm:test")
    manifest = adapter.parse_manifest(SCORM_12)
    assert manifest.identifier == "PKG-1"
    assert manifest.version == "1.2"
    assert manifest.title == "Intro to Fractions"
    assert manifest.launch_href == "lesson1.html"
    assert len(manifest.resources) == 2
    sco = [r for r in manifest.resources if r.scorm_type == "sco"]
    assert len(sco) == 1 and sco[0].href == "lesson1.html"


def test_scorm_empty_raises():
    raised = False
    try:
        SCORMAdapter("scorm:test").parse_manifest("")
    except SCORMParseError:
        raised = True
    assert raised


def test_scorm_non_manifest_root_raises():
    raised = False
    try:
        SCORMAdapter("scorm:test").parse_manifest("<notmanifest/>")
    except SCORMParseError:
        raised = True
    assert raised
