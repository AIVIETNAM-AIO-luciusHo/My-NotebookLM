# Phiếu duyệt ứng viên bộ vàng (P1.8)

Cách duyệt:
1. Mở PDF ở trang ghi trong khối, đối chiếu "Trích dẫn" với văn bản trên trang (trích dẫn lấy bằng pypdf nên có thể dính chữ/méo ký hiệu; chỉ cần đúng nghĩa).
2. Câu hỏi phải tiếng Việt tự nhiên, không chứa sẵn đáp án, và trả lời được từ trích dẫn mà không cần kiến thức ngoài tài liệu.
3. Đáp án phải đúng so với PDF: đánh dấu [x] Đúng, hoặc [x] Sai (sửa đáp án ở dòng ghi chú).
4. Câu mơ hồ, trùng ý câu khác, hoặc quote lệch trang: đánh dấu [x] Loại.
5. Chỉ chủ dự án đổi `reviewed` thành true; mọi câu hiện là reviewed:false, proposed_by:model.


## math-linear-regression.pdf

### c01 — trang 14 — fact / prose

- Câu hỏi: Theo tài liệu, nếu thay đổi giả định về phân phối nhiễu thì điều gì thay đổi theo, và nhiễu Laplace dẫn tới hàm mất mát nào?
- Đáp án: Hàm mất mát thay đổi theo giả định nhiễu; nhiễu Laplace cho MAE (nhiễu có ngoại lai cho Huber).
- Trích dẫn: Đổi giả định thì đổi hàm mất mát: nhiễu Laplace cho MAE, nhiễu có ngoại lai cho Huber.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c02 — trang 14 — fact / table

- Câu hỏi: Trong bảng ba hàm mất mát của khoá học, hàm nào ứng với giả định nhiễu Laplace và nó có đặc điểm gì?
- Đáp án: MAE: bền với ngoại lai nhưng không khả vi tại 0.
- Trích dẫn: Laplace MAE1 n∑|yi−ˆyi| Bền ngoại lai, không khả vi tại 0
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c07 — trang 17 — fact / formula

- Câu hỏi: Điều kiện nào của ma trận X bảo đảm nghiệm cực tiểu của bài toán bình phương tối thiểu là duy nhất và có dạng (X⊤X)^-1 X⊤y?
- Đáp án: X phải đủ hạng cột.
- Trích dẫn: NếuXđủ hạng cột thì nghiệm cực tiểu duy nhất của∥y−Xw∥2là ˆw= (X⊤X)−1X⊤y. (8)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c08 — trang 26 — fact / prose

- Câu hỏi: Khi số đặc trưng nhiều hơn số mẫu, việc cộng λI vào X⊤X trong Ridge ảnh hưởng thế nào đến tính khả nghịch của ma trận?
- Đáp án: Ma trận X⊤X+λI luôn khả nghịch với λ>0, kể cả khi d>n.
- Trích dẫn: cộng λIlàm ma trận luôn khả nghịch , kể cả khid>n.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c09 — trang 30 — fact / table

- Câu hỏi: Trong bảng so sánh ba dạng chính quy hoá, dạng nào có nghiệm dạng đóng và những dạng nào cho nghiệm thưa?
- Đáp án: Chỉ Ridge có nghiệm dạng đóng; Lasso và ElasticNet cho nghiệm thưa.
- Trích dẫn: Nghiệm đóng Có Không Không Nghiệm thưa Không Có Có
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c11 — trang 8, 26 — multi-hop / prose

- Câu hỏi: Khi số đặc trưng nhiều hơn số mẫu thì điều gì xảy ra với X⊤X, và Ridge xử lý vấn đề đó bằng cách nào?
- Đáp án: X không đủ hạng cột nên X⊤X suy biến và (X⊤X)^-1 không tồn tại; Ridge cộng λI nên ma trận luôn khả nghịch với λ>0.
- Trích dẫn: Khid>n(nhiều đặc trưng hơn mẫu — rất thường gặp trong genomics, NLP), X không thể đủ hạng cột. Khi đó X⊤Xsuy biến, nghiệm OLS không duy nhất, và (X⊤X)−1không tồn tại. [...] Ma trận X⊤X+λIluôn khả nghịch với λ>0
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c12 — trang 12, 20 — multi-hop / table

- Câu hỏi: Vì sao QR hoặc SVD được ưa dùng hơn phương trình chuẩn trong sản xuất, dù có thể chậm hơn?
- Đáp án: Phương trình chuẩn bình phương số điều kiện, còn QR và SVD làm việc trực tiếp trên X nên chỉ chịu cond(X).
- Trích dẫn: Bình phương số điều kiện là lý do kỹ thuật quan trọng nhất để khôngdùng phương trình chuẩn trong sản xuất. Nếu cond(X) = 106thìcond(X⊤X) = 1012— vượt độ chính xác của float64 (≈1016) một cách nguy hiểm. QR và SVD làm việc trực tiếp trên Xnên chỉ chịu cond(X). [...] Bảng 2: So sánh bộ giải. Cột số điều kiện là lý do QR/SVD được ưa dùng dù chậm hơn: chúng không bình phương sai số như phương trình chuẩn.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c13 — trang 26, 29 — multi-hop / formula

- Câu hỏi: Hai dạng chính quy hoá L2 (Ridge) và L1 (Lasso) tương ứng với các phân phối tiên nghiệm nào của trọng số?
- Đáp án: Ridge tương ứng tiên nghiệm Gauss (MAP Gauss); Lasso tương ứng tiên nghiệm Laplace (MAP Laplace).
- Trích dẫn: Định lý 8.1 (Ridge =MAP Gauss) .Với tiên nghiệm w∼N (0,τ2I)và nhiễuN(0,σ2), [...] Định lý 9.1 (Lasso =MAP Laplace) .Với tiên nghiệm Laplace p(wj)∝exp(−|wj|/b) độc lập theo từng chiều,
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c03 — trang 11 — number / formula

- Câu hỏi: So với số điều kiện của X, số điều kiện của ma trận X⊤X lớn hơn thế nào?
- Đáp án: Bằng bình phương: cond(X⊤X) = cond(X)^2.
- Trích dẫn: Nghiêm trọng hơn: cond(X⊤X) = cond(X)2.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c04 — trang 12 — number / formula

- Câu hỏi: Nếu số điều kiện của X cỡ một triệu thì số điều kiện của ma trận trong phương trình chuẩn là bao nhiêu và vì sao điều đó đáng ngại với float64?
- Đáp án: Khoảng 10^12, rất gần giới hạn độ chính xác của float64 (khoảng 10^16) nên nguy hiểm.
- Trích dẫn: Nếu cond(X) = 106thìcond(X⊤X) = 1012— vượt độ chính xác của float64 (≈1016)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c05 — trang 20 — number / table

- Câu hỏi: Trong bảng so sánh các bộ giải hồi quy, phân rã QR có độ phức tạp thế nào và được khuyên dùng trong trường hợp nào?
- Đáp án: O(nd^2), số điều kiện cond(X); là mặc định an toàn cho bài toán cỡ vừa.
- Trích dẫn: Phân rã QR O(nd2) cond( X) Mặc định an toàn cho bài toán vừa
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c06 — trang 20 — number / formula

- Câu hỏi: Với hàm mất mát trung bình bình phương, tốc độ học η phải nằm trong khoảng nào thì gradient descent hội tụ?
- Đáp án: 0 < η < 2/λmax, với λmax là trị riêng lớn nhất của (2/n)X⊤X.
- Trích dẫn: gradient descent hội tụ khi và chỉ khi 0<η<2 λmax, λ max=trị riêng lớn nhất của2 nX⊤X. (9)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c10 — trang 36 — number / prose

- Câu hỏi: Chỉ số VIF vượt ngưỡng nào thì tài liệu coi là báo hiệu đa cộng tuyến nghiêm trọng?
- Đáp án: VIF lớn hơn 10.
- Trích dẫn: VIF>10báo hiệu đa cộng tuyến nghiêm trọng.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 


## module3-trees-xai-timeseries.pdf

### c14 — trang 7 — fact / formula

- Câu hỏi: Vì sao sai số phân loại không phải là độ đo tốt để mọc cây, dù nó cũng là một độ bất thuần?
- Đáp án: Vì nó lõm nhưng tuyến tính từng khúc, nên độ giảm bất thuần ΔI có thể bằng 0 cho những phép chia thực sự hữu ích.
- Trích dẫn: Độ đo 1−maxkpklõm nhưng tuyến tính từng khúc , nên ∆Icó thể bằng 0cho những phépchiathựcsựhữuích.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c16 — trang 8 — fact / table

- Câu hỏi: Trong bảng ba thuật toán cây kinh điển, thuật toán nào luôn chia nhị phân và dùng tiêu chí gì?
- Đáp án: CART, dùng Gini/MSE, hồi quy lẫn phân loại và có cắt tỉa.
- Trích dẫn: CART Gini / MSE Luôn nhị phân Hồi quy lẫn phân loại, có cắt tỉa
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c18 — trang 11 — fact / formula

- Câu hỏi: Phương sai của trung bình B biến ngẫu nhiên cùng phương sai σ² và tương quan đôi một ρ có dạng nào?
- Đáp án: ρσ² + (1−ρ)σ²/B.
- Trích dẫn: Định lý 3.3 (Phương sai của trung bình các ước lượng tương quan) .ChoBbiến ngẫu nhiên cùng phương sai σ2, tương quan đôi một bằng ρ. Khi đó Var(1 BB∑ b=1Xb) =ρσ2+1−ρ Bσ2. (5)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c20 — trang 15 — fact / table

- Câu hỏi: Trong bảng các mất mát của GBM, với mất mát tuyệt đối thì phần dư giả là gì và đặc điểm nổi bật ra sao?
- Đáp án: Phần dư giả là sgn(y−F); bền với ngoại lai và tối ưu cho trung vị.
- Trích dẫn: Tuyệt đối |y−F| sgn(y−F) Bền, tối ưu trung vị
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c23 — trang 25 — fact / table

- Câu hỏi: Trong bảng so sánh các phương pháp XAI, phương pháp nào dựa trên lý thuyết trò chơi và điểm yếu chính của nó là gì?
- Đáp án: SHAP; điểm yếu là giả định độc lập đặc trưng.
- Trích dẫn: SHAP Cả hai Lý thuyết trò chơiO(TLD2) (cây)Giả định độc lập đặc trưng
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c24 — trang 28 — fact / table

- Câu hỏi: Muốn đọc bậc p của mô hình AR từ đồ thị tự tương quan, ta nhìn ACF hay PACF và dấu hiệu nhận biết là gì?
- Đáp án: Nhìn PACF: PACF cắt đứt sau trễ p (ACF suy giảm dần).
- Trích dẫn: AR(p) Suy giảm dần (mũ/sin tắt dần)Cắt đứt sau trễp Đọcptừ PACF
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c25 — trang 29 — fact / table

- Câu hỏi: Khi dùng trung bình trượt (rolling mean) làm đặc trưng chuỗi thời gian, cửa sổ phải kết thúc ở đâu để không rò rỉ thông tin?
- Đáp án: Phải kết thúc tại thời điểm t, không căn giữa.
- Trích dẫn: Phảikết thúc tại t, không căn giữa
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c26 — trang 7, 8 — multi-hop / prose

- Câu hỏi: Theo tài liệu, tiêu chí nào dùng để mọc cây CART, còn khi cắt tỉa theo độ phức tạp chi phí thì hàm mục tiêu có dạng gì?
- Đáp án: Mọc cây bằng Gini/entropy (sai số phân loại chỉ dùng khi cắt tỉa); cắt tỉa theo Rα(T) = R(T) + α|T| với α ≥ 0.
- Trích dẫn: Đó là lý do CART dùng Gini/entropy để mọccây và chỉ dùng sai số phân loại khi cắt tỉa. [...] Rα(T) =R(T) +α|T|, α≥0. (3)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c27 — trang 19, 29 — multi-hop / prose

- Câu hỏi: CatBoost và đặc trưng cửa sổ của chuỗi thời gian tránh rò rỉ dữ liệu theo cùng một nguyên tắc nào?
- Đáp án: Chỉ dùng thông tin từ quá khứ: CatBoost dùng mã hoá có thứ tự chỉ dựa trên các mẫu đứng trước, còn cửa sổ phải kết thúc tại thời điểm hiện tại, không căn giữa.
- Trích dẫn: Cấu trúc này giống hệt tinh thần của thanh lọc thời gian ở Mục 16: chỉ dùng quá khứ . [...] mọi cửa sổ phải kết thúctại thời điểm hiện tại, không bao giờ căn giữa.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c28 — trang 14, 15 — multi-hop / prose

- Câu hỏi: AdaBoost và Gradient Boosting được tài liệu diễn giải như quá trình tối ưu nào trong không gian hàm?
- Đáp án: AdaBoost là coordinate descent trên mất mát mũ trong không gian hàm; Gradient Boosting hạ gradient trên phiếm hàm mất mát trong không gian hàm.
- Trích dẫn: AdaBoost chính là coordinate descent trên PT (6) trong không gian hàm, [...] XemFnhư một điểmtrong không gian hàm và hạ gradient trên phiếm hàm mất mát.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c15 — trang 7 — number / formula

- Câu hỏi: Một nút hai lớp (400,400) được chia thành (300,100) và (100,300). Độ giảm Gini của phép chia này là bao nhiêu?
- Đáp án: 0.125.
- Trích dẫn: Vídụhailớp (400,400):chiathành (300,100)và(100,300) cho∆I= 0theo sai số phân loại, nhưng ∆Gini = 0.5−(0.5·0.375 + 0.5·0.375) = 0.125>0
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c17 — trang 11 — number / prose

- Câu hỏi: Trong lấy mẫu bootstrap kích thước n, khoảng bao nhiêu phần trăm mẫu không được chọn lần nào (cơ sở của ước lượng OOB)?
- Đáp án: Khoảng 36.8% (tiến tới e^-1).
- Trích dẫn: Khoảng 36.8%số mẫu nằm ngoài mỗi bootstrap, tạo thành tập kiểm định miễn phí
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c19 — trang 14 — number / formula

- Câu hỏi: Trong AdaBoost, một bộ học yếu có sai số có trọng số bằng một nửa thì được gán hệ số αm bằng bao nhiêu và điều đó nghĩa là gì?
- Đáp án: αm = 0: bộ học ngang tung đồng xu nên bị bỏ qua hoàn toàn.
- Trích dẫn: thìαm= 0: bộ học ngang với tung đồng xu, bị bỏ qua hoàn toàn.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c21 — trang 15 — number / formula

- Câu hỏi: Trong XGBoost, trọng số lá tối ưu w*_j được tính từ tổng gradient Gj, tổng hessian Hj và hệ số λ như thế nào?
- Đáp án: w*_j = −Gj / (Hj + λ).
- Trích dẫn: w⋆ j=−Gj Hj+λ,J⋆=−1 2T∑ j=1G2 j Hj+λ+γT, (11)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c22 — trang 24 — number / prose

- Câu hỏi: Để tính chính xác giá trị Shapley cho mô hình boosting 5 đặc trưng, tài liệu phải liệt kê bao nhiêu tập con?
- Đáp án: 32 tập con (2^5).
- Trích dẫn: Trong Mục 17 ta tính ϕjchính xác bằng cách liệt kê toàn bộ 25= 32tập con cho một mô hình boosting 5đặc trưng.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 


## module4-deeplearning-optimization.pdf

### c33 — trang 17 — fact / formula

- Câu hỏi: Trong lịch trình cosine annealing kèm warmup, learning rate ở giai đoạn warmup (t ≤ Tw) thay đổi theo quy luật nào?
- Đáp án: Tăng tuyến tính: ηt = ηmax·t/Tw.
- Trích dẫn: ηmaxt Tw, t ≤Tw(warmup tuyến tính)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c34 — trang 29 — fact / table

- Câu hỏi: Trong bảng so sánh hàm kích hoạt, ReLU có miền giá trị nào và vấn đề chính của nó là gì?
- Đáp án: Miền giá trị [0,∞); vấn đề chính là Dead ReLU.
- Trích dẫn: ReLU [0,∞){0,1} Không Dead ReLU
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c35 — trang 30 — fact / formula

- Câu hỏi: Đạo hàm riêng của đầu ra softmax pi theo logit zj trong trường hợp i khác j bằng gì?
- Đáp án: −pi·pj.
- Trích dẫn: Trường hợp i̸=j.Tử sốezikhông phụ thuộc zj, nên ∂pi ∂zj=ezi·( −1 S2) ·ezj=−ezi S·ezj S=−pipj.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c38 — trang 38 — fact / table

- Câu hỏi: Trong bảng so sánh các sơ đồ chuẩn hoá, sơ đồ nào gộp theo từng mẫu, không phụ thuộc kích thước lô và dùng cho Transformer?
- Đáp án: LayerNorm.
- Trích dẫn: LayerNorm (C)với mỗiN Không Transformer, RNN, Bnhỏ
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c40 — trang 34, 35 — multi-hop / formula

- Câu hỏi: Với mạng ReLU, phương sai trọng số trong khởi tạo He là bao nhiêu và hệ số ở tử số đó có vai trò gì?
- Đáp án: Var(w) = 2/nin; hệ số 2 bù cho một nửa tín hiệu bị ReLU cắt bỏ.
- Trích dẫn: Với kích hoạt ReLU, điều kiện bảo toàn phương sai chiều tiến là Var(w) =2 nin. (59) [...] Hệ số 2ở tử số chính là để bù cho một nửa tín hiệu bị ReLU cắt bỏ.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c41 — trang 28, 29 — multi-hop / table

- Câu hỏi: Giá trị lớn nhất của đạo hàm sigmoid là bao nhiêu, và bảng so sánh hàm kích hoạt ghi vấn đề chính của sigmoid là gì?
- Đáp án: Đạo hàm sigmoid tối đa 1/4 (tại z=0); vấn đề chính là bão hoà hai phía, triệt tiêu gradient.
- Trích dẫn: Hệ quả 11.2 (Chặn trên của đạo hàm sigmoid) .maxzσ′(z) = 1/4, đạt tạiz= 0. [...] Sigmoid (0,1) (0 ,1/4] Không Bãohoàhaiphía,triệt tiêu gradient
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c42 — trang 38, 39 — multi-hop / prose

- Câu hỏi: Vì sao chế độ ngược của vi phân tự động phù hợp với học sâu hơn chế độ thuận, và nó phải đánh đổi điều gì?
- Đáp án: Mất mát vô hướng (m=1) và số đầu vào n rất lớn nên chế độ ngược cho cả gradient trong một lượt, đổi lại phải tốn bộ nhớ lưu đồ thị.
- Trích dẫn: Mỗi lượt cho một hàng củaJ, tức gradient của mộtđầu ra (VJP). [...] Học sâu luôn có m= 1 (mất mát vô hướng) và nkhổng lồ, nên chế độ ngược thắng tuyệt đối — đổi lại phải trả giá bằng bộ nhớ lưu đồ thị.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c29 — trang 11 — number / table

- Câu hỏi: Trong bảng ba biến thể gradient descent, biến thể nào dùng đúng một mẫu mỗi bước và chi phí mỗi bước là bao nhiêu?
- Đáp án: SGD thuần, chi phí O(d) mỗi bước.
- Trích dẫn: SGD thuần 1 O(d) Nhiễu rất lớn, thoát điểm yên ngựa tốt, không tận dụng được vector hoá
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c30 — trang 11 — number / prose

- Câu hỏi: Nếu tăng kích thước lô gấp 4 lần thì độ lệch chuẩn của nhiễu gradient thay đổi ra sao?
- Đáp án: Giảm đi một nửa (tỉ lệ 1/√B), trong khi chi phí tính toán tăng 4 lần.
- Trích dẫn: Độ lệch chuẩn của nhiễu gradient tỉ lệ1/√ B. Tăng lô gấp 4lần chỉ giảm nhiễu một nửa, trong khi chi phí tính toán tăng 4lần.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c31 — trang 14 — number / formula

- Câu hỏi: Các giá trị mặc định của siêu tham số β1, β2 và ε trong Adam là bao nhiêu?
- Đáp án: β1 = 0.9, β2 = 0.999, ε = 10^-8.
- Trích dẫn: Mặc định:β1= 0.9,β2= 0.999,ϵ= 10−8.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c32 — trang 16 — number / table

- Câu hỏi: Với mô hình 7 tỉ tham số, trạng thái của Adam cần thêm khoảng bao nhiêu bộ nhớ ở độ chính xác fp32?
- Đáp án: Khoảng 56GB.
- Trích dẫn: với mô hình 7tỉ tham số, Adam cần thêm 56GB chỉ để lưu trạng thái ở độ chính xác fp32.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c36 — trang 34 — number / formula

- Câu hỏi: Để bảo toàn phương sai tín hiệu ở cả chiều tiến và chiều ngược, khởi tạo Xavier đặt phương sai trọng số theo nin và nout như thế nào?
- Đáp án: Var(w) = 2/(nin + nout).
- Trích dẫn: Để phương sai được bảo toàn theo cả chiều tiến lẫn chiều ngược, cần Var(w) =2 nin+nout. (58)
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c37 — trang 35 — number / table

- Câu hỏi: Nếu dùng khởi tạo Xavier cho mạng ReLU thì phương sai tín hiệu co lại bao nhiêu mỗi tầng, và sau L tầng còn lại bao nhiêu?
- Đáp án: Co lại hệ số 1/2 mỗi tầng; sau L tầng còn 2^-L.
- Trích dẫn: Sai lầm phổ biến: dùng Xavier cho mạng ReLU — khi đó phương sai co lại hệ số 1/2mỗi tầng, sau Ltầng còn 2−L.
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 

### c39 — trang 39 — number / formula

- Câu hỏi: Khi dùng gradient checkpointing cho mạng L tầng, số điểm mốc tối ưu k và bộ nhớ tương ứng là bao nhiêu?
- Đáp án: k = √L, cho bộ nhớ O(√L).
- Trích dẫn: Tối ưu tạik=√ L, cho bộ nhớ O(√ L).
- Duyệt: [ ] Đúng  [ ] Sai  [ ] Loại
- Ghi chú: 
