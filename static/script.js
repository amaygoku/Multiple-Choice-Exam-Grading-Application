document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const answersInput = document.getElementById('correct-answers-input');
    
    // Areas
    const loadingState = document.getElementById('loading-state');
    const resultsSection = document.getElementById('results-section');
    const btnReset = document.getElementById('btn-reset');

    // UI Elements
    const txtName = document.getElementById('ocr-name');
    const txtMssv = document.getElementById('ocr-mssv');
    const txtMade = document.getElementById('ocr-made');
    
    const cropName = document.getElementById('crop-name');
    const cropMssv = document.getElementById('crop-mssv');
    const cropMade = document.getElementById('crop-made');
    
    const resultImg = document.getElementById('result-img');
    const answersGrid = document.getElementById('answers-grid');
    const totalAnswersSpan = document.getElementById('total-answers');

    const gradingSummary = document.getElementById('grading-summary');
    const finalScore = document.getElementById('final-score');
    const finalCorrect = document.getElementById('final-correct');

    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', e => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));

    dropZone.addEventListener('drop', e => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', e => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });

    btnReset.addEventListener('click', () => {
        resultsSection.classList.add('hidden');
        dropZone.style.display = 'block';
        fileInput.value = '';
    });

    // Camera features
    const btnToggleCamera = document.getElementById('btn-toggle-camera');
    const cameraSection = document.getElementById('camera-section');
    const cameraFeed = document.getElementById('camera-feed');
    const btnTakePhoto = document.getElementById('btn-take-photo');
    const cameraCanvas = document.getElementById('camera-canvas');
    let stream = null;

    btnToggleCamera.addEventListener('click', async () => {
        if (cameraSection.style.display === 'none') {
            cameraSection.style.display = 'block';
            dropZone.style.display = 'none';
            btnToggleCamera.innerHTML = '<i class="ri-image-add-line"></i> Dùng Tải Ảnh Lên';
            try {
                // Yêu cầu độ phân giải cao nhất có thể (lên tới 4K) để OCR không bị mờ
                const constraints = {
                    video: {
                        facingMode: "environment",
                        width: { ideal: 4096 },
                        height: { ideal: 2160 }
                    }
                };
                stream = await navigator.mediaDevices.getUserMedia(constraints);
                cameraFeed.srcObject = stream;
            } catch (e) {
                alert('Không thể mở camera: ' + e.message);
            }
        } else {
            cameraSection.style.display = 'none';
            dropZone.style.display = 'block';
            btnToggleCamera.innerHTML = '<i class="ri-camera-lens-line"></i> Dùng Camera / Khung Hướng Dẫn';
            if (stream) {
                stream.getTracks().forEach(t => t.stop());
                stream = null;
            }
        }
    });

    btnTakePhoto.addEventListener('click', () => {
        if (!cameraFeed.videoWidth) return;
        cameraCanvas.width = cameraFeed.videoWidth;
        cameraCanvas.height = cameraFeed.videoHeight;
        const ctx = cameraCanvas.getContext('2d');
        ctx.drawImage(cameraFeed, 0, 0);
        cameraCanvas.toBlob(blob => {
            const file = new File([blob], "camera_capture.png", { type: "image/png" });
            handleFile(file);
            if (stream) {
                stream.getTracks().forEach(t => t.stop());
                stream = null;
            }
            cameraSection.style.display = 'none';
            btnToggleCamera.innerHTML = '<i class="ri-camera-lens-line"></i> Dùng Camera / Khung Hướng Dẫn';
        }, 'image/png');
    });

    function setImageSafe(el, src) {
        if(src) {
            el.src = src;
            el.style.display = 'block';
        } else el.style.display = 'none';
    }

    function handleFile(file) {
        dropZone.style.display = 'none';
        loadingState.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('correct_answers', answersInput.value);

        fetch('/upload', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            loadingState.classList.add('hidden');
            if(data.success) showResults(data);
            else {
                alert('Lỗi server: ' + data.error);
                dropZone.style.display = 'block';
            }
        })
        .catch(err => {
            console.error(err);
            loadingState.classList.add('hidden');
            dropZone.style.display = 'block';
            alert('Lỗi mạng!');
        });
    }

    function showResults(data) {
        // Visual
        resultImg.src = data.result_image_url;

        // Info
        txtName.innerText = data.student_info.name || "Không rõ";
        txtMssv.innerText = data.student_info.mssv || "???";
        txtMade.innerText = data.student_info.ma_de || "???";

        setImageSafe(cropName, data.crops.ho_va_ten);
        setImageSafe(cropMssv, data.crops.mssv);
        setImageSafe(cropMade, data.crops.ma_de);

        // Grade
        answersGrid.innerHTML = '';
        totalAnswersSpan.innerText = `${data.answers.length} câu`;

        if (data.grading) {
            gradingSummary.style.display = 'block';
            finalScore.innerText = data.grading.score;
            finalCorrect.innerText = `${data.grading.correct_count} / ${data.grading.total}`;
            
            data.grading.details.forEach(det => {
                const item = document.createElement('div');
                item.className = 'answer-item';
                const color = det.result === "ĐÚNG" ? '#10b981' : (det.result === "SAI" || det.result === "CHƯA TÔ" ? '#ef4444' : '#f59e0b');
                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between; width:100%;">
                        <span class="q-num">Câu ${det.question}</span>
                        <div>
                            <span class="a-val" style="color: white; margin-right: 10px;">Làm: ${det.student_ans}</span>
                            <span style="color: ${color}; font-weight:bold; font-size: 0.85rem">${det.result} (Gốc: ${det.correct_ans})</span>
                        </div>
                    </div>
                `;
                answersGrid.appendChild(item);
            });
        } else {
            gradingSummary.style.display = 'none';
            data.answers.forEach((ans, idx) => {
                const item = document.createElement('div');
                item.className = 'answer-item';
                const display = ans || 'Trống';
                item.innerHTML = `
                    <span class="q-num">Câu ${idx + 1}</span>
                    <span class="a-val">${display}</span>
                `;
                answersGrid.appendChild(item);
            });
        }

        resultsSection.classList.remove('hidden');
    }
});
