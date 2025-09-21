from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from svm_predictor import Predictor
from gpt_predictor import DomainClassifier

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 加载训练好的小模型
predictor = Predictor(
    model_path='linear_svc_model.pkl',
    label_mapping_path='label_mapping.pkl',
    scaler_path='scaler.pkl',
    keyword_dict_path='keyword_dict.pkl'
)

@app.route("/domain", methods=["POST", "OPTIONS"])
def keyword_post():
    if request.method == "OPTIONS":
        return '', 200

    #获取readme和api_key
    data = request.get_json()
    text = data.get("text", "")
    api_key = data.get("api_key", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if not api_key:
        return jsonify({"error": "No api_key provided"}), 400

    # 设置传入的 openai key
    openai.api_key = api_key

    # 获取keyword
    messages = [
        {"role": "system", "content": (
            "你是一个开源软件项目的标签标注员，负责根据项目描述自动生成适合的 GitHub 标签。"
            "请根据给定的项目描述，结合 GitHub 标签的惯例，为该项目分配标签。标签应该简洁、相关，"
            "并能准确反映项目的主要特点，不低于六个除非文本过短。输出的格式应为：tag1 tag2 tag3...，多个标签之间用空格分隔。"
            "若文本过短无法提取标签则输出 none。请确保标签的数量和准确性，以便更好地描述项目的性质。"
        )},
        {"role": "user", "content": f"Project description: {text}"}
    ]

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0
        )
        tags = response.choices[0].message.content.strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # 小模型预测
    try:
        if tags.strip().lower() == "none":
            svm_result = []
        else:
            svm_result = predictor.predict_from_keyword(tags)
    except Exception as e:
        return jsonify({"error": "SVM预测失败: " + str(e)}), 500

    # 大模型预测
    if not svm_result:
        return jsonify({
            "tags": tags,
            "result": "",
            "svm_result": svm_result
        })

    # 比较前两名概率
    prob1 = svm_result[0]['prob'] if len(svm_result) > 0 else 0.0
    prob2 = svm_result[1]['prob'] if len(svm_result) > 1 else 0.0

    if prob1 - prob2 < 0.15:
        return jsonify({
            "tags": tags,
            "result": svm_result[0]['class'],
            "svm_result": svm_result
        })
    else:
        try:
            domain_classifier = DomainClassifier(api_key=api_key)
            prediction_dict = {}
            for i in range(min(len(svm_result), 12)):
                prediction_dict[f"Top{i + 1} Class"] = svm_result[i]['class']
                prediction_dict[f"Top{i + 1} Probability"] = svm_result[i]['prob']
            result = domain_classifier.classify(readme_text=text, prediction_dict=prediction_dict)
        except Exception as e:
            return jsonify({"error": "大模型判定失败: " + str(e)}), 500

        return jsonify({
            "tags": tags,
            "result": result,
            "svm_result": svm_result
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
