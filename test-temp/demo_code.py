from pathlib import Path
import time
import pandas as pd
from sklearn.metrics import accuracy_score
from sklearn.metrics import classification_report, confusion_matrix
from datasets import load_dataset
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
datasets = load_dataset("stanfordnlp/imdb",split='test')
print(type(datasets))

model = init_chat_model(
    model = "deepseek-flash",
    model_provider="openai",
    base_url = os.getenv("DEEPSEEK_FLASH_URL"),
    api_key = os.getenv("DEEPSEEK_FLASH_KEY"),
)
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """
You are a professional movie review sentiment classifier.

Your task is to classify a movie review into one of two categories:

positive
negative

Rules:
1. Consider the overall sentiment of the review.
2. Return only one word: positive or negative.
3. Do not provide explanations.
"""
    ),
    (
        "human",
        "Movie review:\n{review}"
    )
])


# 分别筛选正面和负面评论
negative = datasets.filter(lambda x: x["label"] == 0)
positive = datasets.filter(lambda x: x["label"] == 1)

# 随机抽取，每类 50 条
negative = negative.shuffle(seed=42).select(range(50))
positive = positive.shuffle(seed=42).select(range(50))

# 合并数据
samples = list(negative) + list(positive)

df = pd.DataFrame(samples)

# 保存 CSV
df.to_csv("imdb_100.csv", index=False, encoding="utf-8-sig")

print(df.head())
print("数据集保存成功！")


chain = prompt | model | StrOutputParser()

def predict_sentiment(text: str) -> int:

    result = chain.invoke({
        "review": text
    })

    result = result.strip().lower()

    if result == "positive":
        return 1

    if result == "negative":
        return 0

    raise ValueError(f"Invalid model output: {result!r}")


BASE_DIR = Path(__file__).resolve().parent.parent
df = pd.read_csv(BASE_DIR / "imdb_100.csv")

output_path = BASE_DIR / "labeling_results.csv"

if output_path.exists():
    saved_df = pd.read_csv(output_path)


    if (
        len(saved_df) != len(df)
        or not saved_df["text"].equals(df["text"])
    ):
        raise ValueError("历史结果与当前数据不一致")

    df = saved_df
else:
    df["model_label"] = pd.Series(
        [pd.NA] * len(df),
        dtype="Int64"
    )

for index, row in df.iterrows():

    if pd.notna(row["model_label"]):
        continue

    try:
        prediction = predict_sentiment(
            str(row["text"])
        )

        df.at[index, "model_label"] = prediction

        print(
            f"[{index + 1}/{len(df)}] "
            f"Human: {row['label']} | "
            f"Model: {prediction}"
        )

    except Exception as e:
        print(f"Error at row {index}: {e}")

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    time.sleep(0.3)



# 7. 评估
valid_df = df.dropna(
    subset=["model_label"]
).copy()

if valid_df.empty:
    print("No valid predictions.")
else:
    y_true = valid_df["label"].astype(int)
    y_pred = valid_df["model_label"].astype(int)

    print("\nAccuracy:")
    print(accuracy_score(y_true, y_pred))

    print("\nClassification Report:")
    print(
        classification_report(
            y_true,
            y_pred,
            labels=[0, 1],
            target_names=["negative", "positive"],
            zero_division=0
        )
    )

    print("\nConfusion Matrix:")
    print(
        confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1]
        )
    )

    # 保存错误样本
    errors = valid_df[
        y_true != y_pred
    ]

    errors.to_csv(
        BASE_DIR / "error_samples.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print(f"\n错误样本: {len(errors)}")
