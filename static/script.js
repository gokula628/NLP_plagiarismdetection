// =========================================================
// ACADEMIC PLAGIARISM & AI DETECTION SYSTEM - FRONTEND SCRIPT
// =========================================================

document.addEventListener("DOMContentLoaded", () => {
    console.log("NLP Plagiarism & AI Text Detection System initialized.");

    // Sync hover & scroll between Document 1 and Document 2 highlights
    const marks1 = document.querySelectorAll("#diff-box1 mark");
    const marks2 = document.querySelectorAll("#diff-box2 mark");

    marks1.forEach(mark => {
        mark.addEventListener("mouseenter", () => {
            const matchId = mark.getAttribute("data-match");
            if (!matchId) return;

            // Find matching mark in Doc 2
            const targetMark = document.querySelector(`#diff-box2 mark[data-match="${matchId}"]`);
            if (targetMark) {
                targetMark.style.outline = "2px solid #23458f";
                targetMark.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
            mark.style.outline = "2px solid #23458f";
        });

        mark.addEventListener("mouseleave", () => {
            const matchId = mark.getAttribute("data-match");
            if (!matchId) return;

            const targetMark = document.querySelector(`#diff-box2 mark[data-match="${matchId}"]`);
            if (targetMark) targetMark.style.outline = "none";
            mark.style.outline = "none";
        });
    });
});