from backend.graph_db import medical_kg

test_input = "我感觉胸闷、心悸，还有点呼吸困难，手脚无力。"
print(f"Test Input: {test_input}")

symptoms = medical_kg.extract_symptoms(test_input)
print(f"Extracted Symptoms: {symptoms}")

context = medical_kg.get_context_for_symptoms(symptoms)
print("\nGenerated Context:")
print(context)

if "胸闷" in symptoms and "心悸" in symptoms and "呼吸困难" in symptoms:
    print("\nSUCCESS: Dynamic extraction works for multiple symptoms.")
else:
    print("\nFAILURE: Some symptoms were not extracted.")
