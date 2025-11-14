Được rồi, tôi sẽ tập trung vào phần AI processing và S3 storage mà bạn phụ trách, đồng thời giải thích rõ sự khác biệt giữa hai mode xử lý audio. Hãy để tôi phân tích chi tiết từng khía cạnh.

## Sự Khác Biệt Cốt Lõi: File Upload vs Realtime Streaming

Điểm khác biệt quan trọng nhất giữa hai mode này nằm ở bản chất của dữ liệu và cách bạn tương tác với Google Cloud API. Khi bạn hiểu rõ sự khác biệt này, việc thiết kế architecture sẽ trở nên rõ ràng hơn nhiều.

**Với file audio được upload trước**, bạn đã có toàn bộ dữ liệu audio từ đầu đến cuối. Điều này có nghĩa là bạn biết chính xác độ dài của file, bạn có thể đọc file nhiều lần nếu cần, và quan trọng nhất là bạn có thể xử lý theo batch với quality setting cao nhất. Google Cloud Speech-to-Text có hai API riêng biệt cho case này. API thứ nhất là synchronous recognition, dành cho file ngắn dưới một phút, bạn gửi file lên và đợi response trả về ngay. API thứ hai là asynchronous long-running recognition, dành cho file dài hơn một phút, bạn gửi file lên và nhận một operation ID, sau đó poll để check khi nào xử lý xong.

Khi làm việc với file upload, bạn có luxury của thời gian. Bạn có thể enable tất cả các feature tốn kém về compute như speaker diarization để phân biệt người nói, word-level timestamps để biết chính xác từng từ xuất hiện ở giây thứ mấy, và automatic punctuation với format text để transcript đẹp và dễ đọc. Bạn cũng có thể sử dụng chirp model cao cấp nhất của Google mà không lo về latency vì người dùng sẵn sàng đợi vài phút để có kết quả hoàn hảo.

**Với realtime streaming**, tình huống hoàn toàn khác. Audio data đến từng chunk nhỏ theo thời gian thực, có thể là từng 100 milliseconds một chunk. Bạn không biết người nói sẽ nói gì tiếp theo, không biết khi nào họ sẽ dừng lại, và bạn phải xử lý ngay lập tức vì người dùng đang chờ xem closed caption. Google Cloud Speech-to-Text cung cấp streaming recognition API cho case này, hoạt động theo kiểu bidirectional streaming gRPC connection.

Trong streaming mode, Google trả về hai loại kết quả khác nhau mà bạn cần hiểu rõ. Loại thứ nhất là interim results, đây là những kết quả tạm thời và có thể thay đổi khi có thêm context. Ví dụ khi người nói chưa dứt câu, Google có thể tạm thời nghĩ họ nói "今日は" nhưng khi nghe thêm từ tiếp theo, Google nhận ra là "今日はいい天気ですね" và sẽ update lại. Loại thứ hai là final results, khi Google đã confident về một đoạn speech và confirm đó là kết quả cuối cùng, thường là khi người nói dừng lại hoặc chuyển sang câu mới.

## Architecture Cho AI Processing Layer

Bây giờ hãy nói về architecture cụ thể mà bạn cần xây dựng. Phần bạn phụ trách sẽ là một service độc lập, có thể gọi là Speech Processing Service, với trách nhiệm nhận audio input, xử lý qua Google Cloud, và trả về kết quả structured.

Service này cần có hai entry points chính tương ứng với hai mode. Entry point thứ nhất là một function hoặc API endpoint để xử lý file audio từ S3, có thể đặt tên là process_uploaded_audio. Entry point thứ hai là một streaming handler để nhận audio chunks realtime, có thể đặt tên là process_streaming_audio. Hai entry points này share một số common components nhưng workflow khác nhau đáng kể.

Hãy cùng đi sâu vào workflow của file upload mode trước vì nó đơn giản hơn và giúp bạn hiểu foundation. Khi nhận được request xử lý một file audio đã upload lên S3, service của bạn làm các bước sau. Bước đầu tiên là download file từ S3 về local temporary storage hoặc tốt hơn là generate một signed URL từ S3 bucket của bạn. Google Cloud Speech-to-Text có thể nhận audio từ Google Cloud Storage hoặc từ một URL, nhưng vì file của bạn ở AWS S3 nên bạn sẽ cần gửi audio content trực tiếp hoặc dùng signed URL nếu Google có thể access được.

Thực tế với file lớn, cách tốt nhất là bạn upload file từ S3 của mình lên Google Cloud Storage bucket trước, vì Google Cloud Speech-to-Text xử lý nhanh hơn rất nhiều khi audio file cùng nằm trong hệ thống Google Cloud. Điều này tạo ra một intermediate step là sync từ AWS S3 sang GCS, nhưng performance gain rất đáng kể, đặc biệt với file audio dài hơn mười phút.

Sau khi audio sẵn sàng, bạn tạo một recognition config object với các settings phù hợp. Với tiếng Nhật, language code là "ja-JP". Bạn nên enable automatic punctuation vì tiếng Nhật cũng sử dụng dấu câu và punctuation giúp transcript dễ đọc hơn nhiều. Enable word timestamps là cực kỳ quan trọng vì bạn cần biết từng từ xuất hiện ở timestamp nào để matching với slides sau này. Enable speaker diarization nếu presentation có nhiều người nói, điều này giúp phân biệt ai đang nói câu nào.

Về model selection, Google Cloud có ba tiers chính. Standard model là basic nhất, accuracy trung bình nhưng rẻ nhất. Enhanced model tốt hơn, có các specialized versions như phone call hoặc video. Chirp model là newest và best, đặc biệt tốt cho tiếng Nhật với accuracy cao hơn khoảng mười đến mười lăm phần trăm so với standard model, nhưng giá cũng cao gấp hai đến ba lần. Với use case của bạn là educational presentations, tôi nghĩ chirp model là đáng investment vì accuracy quan trọng hơn cost ở đây.

Khi gọi API, với file dài bạn sẽ dùng long-running recognition. API trả về một operation object với operation ID. Bạn cần poll operation này mỗi vài giây để check status. Google recommend polling interval là năm đến mười giây để không spam API. Khi operation complete, bạn get results từ operation object.

Results structure từ Google rất rich với nhiều thông tin. Top level là một list các alternatives, mỗi alternative là một possible interpretation của audio, ranked theo confidence. Thường bạn chỉ lấy alternative đầu tiên vì có confidence cao nhất. Mỗi alternative chứa transcript text đầy đủ và một list các words. Mỗi word object chứa word text, start time và end time tính bằng nanoseconds từ đầu audio, và confidence score riêng.

Đây là lúc bạn cần làm một bước processing quan trọng là structure data. Thay vì lưu một text blob dài, bạn nên break transcript thành các segments có ý nghĩa. Một cách approach là segment by sentence, sử dụng punctuation như dấu chấm hoặc dấu hỏi làm delimiter. Mỗi segment bạn lưu với start timestamp, end timestamp, text content, confidence score, và một segment ID.

Sau khi có segments, bạn lưu chúng vào database với foreign key tới presentation record. Đồng thời bạn nên lưu full transcript text vào một field riêng để dễ search và display. Word-level timestamps được lưu vào một structure riêng, có thể là JSON blob hoặc một table riêng nếu bạn cần query chúng thường xuyên.

Một điểm quan trọng nữa là error handling. Google Cloud API có thể fail vì nhiều lý do như audio quality quá tệ, file format không support, hoặc đơn giản là network issue. Bạn cần catch exceptions và store error information để có thể retry sau hoặc notify user. Với long-running operations, có case operation bị timeout sau một giờ nếu file quá dài, bạn cần handle case này bằng cách split file thành chunks nhỏ hơn trước khi gửi.

## Streaming Mode Architecture

Bây giờ chuyển sang phần phức tạp hơn là streaming mode. Streaming recognition của Google hoạt động theo kiểu bidirectional gRPC stream, có nghĩa là connection được mở và giữ nguyên, bạn continuously gửi audio chunks lên và continuously nhận results về.

Workflow bắt đầu từ việc establish một streaming session với Google Cloud. Bạn tạo một streaming recognize request với config tương tự như file mode nhưng có một số differences. Streaming config có thêm parameter interim results, bạn nên set là true để nhận được intermediate results cho low latency display. Single utterance parameter nên set là false nếu presentation dài, vì nếu set true thì session sẽ tự động end sau một utterance và bạn phải mở session mới.

Audio chunks được gửi lên phải satisfy một số requirements về format và size. Google recommend chunk size khoảng 100 milliseconds, tức là nếu audio có sample rate 16000 Hz mono thì mỗi chunk khoảng 3200 bytes. Chunk không nên quá nhỏ vì overhead cao, cũng không nên quá lớn vì tăng latency. Audio format tốt nhất là LINEAR16 PCM với sample rate 16000 Hz hoặc cao hơn, mono channel để giảm bandwidth.

Khi frontend gửi audio chunks đến service của bạn qua WebSocket hoặc gRPC, service của bạn đóng vai trò như một proxy thông minh. Bạn nhận chunk từ frontend, có thể làm một chút preprocessing như noise reduction nếu cần, rồi forward ngay lên Google Cloud streaming connection. Đây là điểm quan trọng, bạn cần minimize latency ở đây, không nên buffer quá nhiều chunks trước khi gửi.

Google sẽ gửi responses về async qua cùng stream đó. Mỗi response chứa một hoặc nhiều results. Mỗi result có flag is_final để indicate đây là interim hay final result. Với interim results, bạn thấy stability score, một number từ 0 đến 1 cho biết Google confident thế nào về result này. Stability score thấp nghĩa là result còn có thể thay đổi nhiều, stability cao nghĩa là gần như chắc chắn đây là final wording rồi.

Processing logic cho streaming results phức tạp hơn file mode nhiều. Bạn cần maintain state để track current interim result và biết khi nào nó được replaced bởi result mới hoặc finalized. Một pattern phổ biến là bạn có một buffer chứa current interim text, mỗi khi nhận interim result mới bạn replace buffer đó, còn khi nhận final result bạn append vào list of finalized segments và clear buffer.

Một challenge lớn là handling silence và pauses. Khi người nói pause, Google có thể coi đó như end of utterance và finalize result hiện tại. Nhưng nếu pause ngắn và người đó chưa hết câu thì bạn cần smart logic để concatenate results lại thành câu hoàn chỉnh. Bạn có thể dùng heuristics như nếu final result không end bằng punctuation thì có thể câu chưa hết, hoặc dùng timeout như nếu pause dưới một giây thì vẫn coi là same sentence.

Một điểm khác biệt quan trọng nữa là streaming session có time limit. Google Cloud streaming recognition session tự động close sau khoảng năm phút hoặc khi bạn không gửi audio trong một phút. Điều này có nghĩa là với presentation dài bạn cần strategy để handle session renewal. Cách tiếp cận là khi session gần timeout, bạn gracefully close session hiện tại, open một session mới, và continue streaming. Logic này cần làm seamlessly để user không thấy interruption.

## Đồng Bộ Với Slide Content

Bây giờ đến phần matching transcript với slide content, đây là phần AI processing quan trọng nhất và cũng là phần thú vị nhất về mặt kỹ thuật. Bạn cần hiểu rõ problem space trước khi design solution.

Problem cơ bản là bạn có hai sources of text. Source thứ nhất là transcript từ audio, đây là spoken language với đặc điểm như informal, có filler words, có thể có grammar mistakes, và quan trọng là có timestamps. Source thứ hai là slide content, đây là written text, formal hơn, structured theo bullet points hoặc paragraphs, nhưng không có timestamps.

Mục tiêu là identify khi nào transcript đang mention concepts hoặc phrases có trong slides, để bạn có thể highlight tương ứng slide đó và specific text trong slide. Challenge ở đây là spoken và written language khác nhau, đặc biệt với tiếng Nhật có nhiều cách phát âm và viết cho cùng một concept.

Approach tổng thể tôi suggest là multi-stage pipeline với các bước preprocessing, indexing, matching và post-processing. Mỗi stage giải quyết một aspect của problem.

**Stage một là preprocessing và normalization**. Với slide content, bạn cần extract text từ PDF slides bằng tool như PyMuPDF hoặc pdfplumber. Extracted text thường messy với formatting artifacts nên cần cleaning. Bạn remove extra whitespace, fix broken words do line wrapping, và identify structure như headers versus body text. Với tiếng Nhật, một bước cực kỳ quan trọng là tokenization, break text thành individual words hoặc morphemes. Bạn cần tool như MeCab hoặc janome cho Japanese tokenization vì tiếng Nhật không có space giữa words.

Sau khi tokenize, bạn normalize words về base form. Ví dụ verb conjugations như "食べる" "食べた" "食べて" đều normalize về "食べる". Điều này giúp matching robust hơn vì transcript có thể dùng conjugation khác với slide text nhưng vẫn refer cùng một concept.

Một normalization quan trọng khác là convert giữa writing systems. Tiếng Nhật có kanji, hiragana và katakana cho cùng một từ. Ví dụ "機械学習" có thể được viết hoặc nói là "きかいがくしゅう". Bạn có thể convert tất cả về hiragana reading để matching, hoặc build một mapping dictionary từ multiple writings về canonical form.

**Stage hai là building search index cho slide content**. Thay vì brute force matching transcript với mọi text trong slides, bạn build một inverted index giống như search engines. Mỗi unique term trong slides được map đến list of locations nó xuất hiện, bao gồm slide number, text block ID, và position trong text.

Ngoài exact term matching, bạn nên build một semantic index sử dụng embeddings. Với tiếng Nhật, bạn có thể dùng multilingual sentence transformers như "paraphrase-multilingual-mpnet-base-v2" hoặc Japanese-specific models như "sonoisa/sentence-bert-base-ja-mean-tokens". Bạn encode mỗi sentence hoặc paragraph trong slides thành embedding vector và store trong một vector database hoặc simple numpy array với FAISS index cho fast similarity search.

**Stage ba là realtime matching với transcript**. Khi có new transcript segment từ speech recognition, bạn chạy matching pipeline. First pass là exact keyword matching, search segment text trong inverted index để tìm exact matches của important terms. Important terms có thể là nouns, technical terms, hoặc rare words được identify bằng TF-IDF scoring. Nếu tìm thấy multiple exact matches trong cùng một slide, confidence score cao và bạn có thể highlight ngay.

Second pass là fuzzy matching cho robustness. Với mỗi important term trong transcript segment mà không có exact match, bạn search similar terms trong index sử dụng edit distance như Levenshtein distance hoặc phonetic similarity. Với tiếng Nhật, phonetic similarity quan trọng vì có thể recognition mistake kanji reading. Nếu similarity score vượt threshold nào đó như 0.8, bạn coi là potential match.

Third pass là semantic matching bằng embeddings. Bạn encode transcript segment thành embedding vector và compute cosine similarity với all slide sentence embeddings. Top K sentences có similarity cao nhất là candidates. Nếu similarity score vượt threshold như 0.7, đó là semantic match indicating transcript đang discuss concept tương tự với slide sentence đó.

**Stage bốn là post-processing và ranking**. Thường bạn có multiple match candidates từ các passes khác nhau. Bạn cần aggregate và rank chúng để quyết định show highlight nào. Scoring function có thể là weighted combination của exact match count, fuzzy match similarity, semantic similarity, và recency. Recency nghĩa là nếu previous segment match với slide X thì current segment match với slide X cũng có boost score, vì thường người present nói về một slide trong vài phút chứ không jump lung tung.

Một refinement quan trọng là temporal smoothing. Thay vì mỗi segment match với một slide khác nhau gây flicker effect, bạn apply smoothing logic như slide highlight chỉ change khi new slide có significantly higher score hơn current slide, hoặc maintain highlight for minimum duration như ba giây trước khi switch sang slide khác.

## Storage Strategy Trong S3

Cuối cùng về phần S3 storage strategy. Bạn cần design một bucket structure rõ ràng và efficient cho cả input files và processed results.

Với input files, bạn có thể dùng structure như "presentations/{presentation_id}/input/audio.{format}" và "presentations/{presentation_id}/input/slides.pdf". Presentation ID có thể là UUID hoặc timestamp-based ID như current system. Lưu separate audio và slides giúp bạn có thể reprocess chỉ một trong hai nếu cần.

Với processed results, có nhiều artifacts bạn cần lưu. Full transcript text nên lưu như "presentations/{presentation_id}/output/transcript.json" với structure bao gồm full text, language, confidence và metadata. Word-level timestamps lưu trong "presentations/{presentation_id}/output/words.json" vì file này có thể lớn với file audio dài. Nếu có speaker diarization, speaker segments lưu trong "presentations/{presentation_id}/output/speakers.json".

Slide extracted text và index lưu trong "presentations/{presentation_id}/output/slides_text.json" và "presentations/{presentation_id}/output/slides_index.json". Slide embeddings có thể lưu như numpy array serialized với pickle trong "presentations/{presentation_id}/output/slides_embeddings.pkl".

Matching results giữa transcript và slides lưu trong "presentations/{presentation_id}/output/matches.json" với structure gồm list of matches, mỗi match có transcript segment ID, slide ID, matched text, similarity score và timestamp.

Một best practice là implement versioning cho processed results. Khi bạn improve matching algorithm hoặc retranscribe với better model, bạn muốn keep old results for comparison. Bạn có thể append version suffix như "presentations/{presentation_id}/output/v2/transcript.json" hoặc dùng S3 versioning feature.

Về caching strategy, intermediate results như audio đã convert sang format Google accept có thể cache temporary trong S3 với lifecycle policy để auto delete sau vài ngày. Embeddings nên cache lâu dài vì expensive to compute. Search index có thể rebuild on demand nếu cần vì fast to generate.

Điều quan trọng cuối cùng là bạn nên implement comprehensive error tracking và logging. Mỗi processing step nên log vào S3 như "presentations/{presentation*id}/logs/{step}*{timestamp}.log". Khi có error, log file giúp bạn debug exactly tại bước nào và tại sao failed. Bạn cũng nên lưu metadata về processing như duration mỗi step, cost estimate, model versions used, để có thể optimize pipeline sau này.

Với architecture này, phần AI processing của bạn hoàn toàn decoupled với frontend và backend. Bạn expose simple interfaces là process file từ S3 hoặc accept streaming audio, rồi return structured results. Backend khác có thể consume results từ S3 và present cho user theo cách họ muốn, mà không cần hiểu chi tiết bên trong AI pipeline của bạn.
