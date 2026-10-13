import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from text_preprocessing import preprocess_text

# ==========================================================
# TF-IDF & N-GRAM TEXT SIMILARITY (LIGHTWEIGHT & FAST)
# ==========================================================

def calculate_similarity(text1, text2):
    processed_text1 = preprocess_text(text1)
    processed_text2 = preprocess_text(text2)

    if not processed_text1.strip() or not processed_text2.strip():
        return 0.0

    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform([processed_text1, processed_text2])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        score = max(0.0, min(100.0, sim * 100))
        return round(score, 2)
    except Exception:
        return 0.0


def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    return sentences


# ==========================================================
# SENTENCE MATCHING FOR VISUAL HIGHLIGHTING
# ==========================================================

def find_matching_sentences(text1, text2):
    sentences1 = split_sentences(text1)
    sentences2 = split_sentences(text2)
    matching_sentences = []

    if not sentences1 or not sentences2:
        return matching_sentences

    for i, s1 in enumerate(sentences1):
        p1 = preprocess_text(s1)
        if not p1.strip():
            continue

        best_score = 0.0
        best_match = None

        for j, s2 in enumerate(sentences2):
            p2 = preprocess_text(s2)
            if not p2.strip():
                continue

            try:
                vec = TfidfVectorizer()
                mat = vec.fit_transform([p1, p2])
                sim = cosine_similarity(mat[0:1], mat[1:2])[0][0] * 100
                if sim > best_score:
                    best_score = sim
                    best_match = s2
            except Exception:
                continue

        if best_score >= 40.0 and best_match:
            matching_sentences.append({
                "sentence1": s1,
                "sentence2": best_match,
                "similarity": round(best_score, 2),
                "level": "high" if best_score >= 70.0 else "moderate"
            })

    return matching_sentences


# ==========================================================
# SIDE-BY-SIDE VISUAL HIGHLIGHTING GENERATOR
# ==========================================================

def generate_highlighted_texts(text1, text2, matching_sentences):
    def escape_html(text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html1 = escape_html(text1)
    html2 = escape_html(text2)

    for idx, match in enumerate(matching_sentences, start=1):
        s1 = match["sentence1"]
        s2 = match["sentence2"]
        level = match["level"]
        css_class = "hl-high" if level == "high" else "hl-mod"

        s1_escaped = escape_html(s1)
        s2_escaped = escape_html(s2)

        replacement1 = f'<mark class="{css_class}" data-match="{idx}" title="Match {idx} ({match["similarity"]}%)">{s1_escaped}</mark>'
        replacement2 = f'<mark class="{css_class}" data-match="{idx}" title="Match {idx} ({match["similarity"]}%)">{s2_escaped}</mark>'

        if s1_escaped in html1:
            html1 = html1.replace(s1_escaped, replacement1, 1)
        if s2_escaped in html2:
            html2 = html2.replace(s2_escaped, replacement2, 1)

    return html1, html2


# ==========================================================
# CLASS-WIDE BATCH ZIP ANALYSIS (OVERALL AVERAGE + HEATMAP)
# ==========================================================

def analyze_zip_batch(file_dict):
    filenames = list(file_dict.keys())
    n = len(filenames)

    if n < 2:
        return {"error": "Zip file must contain at least 2 PDF/DOCX documents to compare."}

    texts = [file_dict[fn] for fn in filenames]
    processed_texts = [preprocess_text(t) for t in texts]

    vectorizer = TfidfVectorizer(ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform(processed_texts)
        sim_matrix = cosine_similarity(tfidf_matrix) * 100
    except Exception:
        sim_matrix = [[0.0]*n for _ in range(n)]

    matrix = []
    top_pairs = []
    total_sim_sum = 0.0
    pair_count = 0

    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                score = 100.0
                status = "Self Match"
            else:
                score = round(max(0.0, min(100.0, float(sim_matrix[i][j]))), 2)
                status = "High Similarity" if score >= 70 else ("Moderate" if score >= 40 else "Low")
                if j > i:
                    total_sim_sum += score
                    pair_count += 1
            
            top_pairs.append({
                "doc1": filenames[i],
                "doc2": filenames[j],
                "similarity": score,
                "status": status
            })
            row.append(score)
        matrix.append(row)

    overall_avg_similarity = round(total_sim_sum / pair_count, 2) if pair_count > 0 else 0.0
    top_pairs.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "filenames": filenames,
        "matrix": matrix,
        "top_pairs": top_pairs,
        "total_documents": n,
        "total_pairs": len(top_pairs),
        "overall_average_similarity": overall_avg_similarity
    }