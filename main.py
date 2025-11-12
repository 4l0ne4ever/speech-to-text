"""
Main script - Test Speech-to-Text System
"""
from presentation_manager import PresentationManager
import os


def main():
    """
    Workflow đơn giản để test hệ thống
    """
    print("=" * 60)
    print("🎤 SPEECH-TO-TEXT SYSTEM")
    print("=" * 60)
    
    # Khởi tạo manager
    manager = PresentationManager()
    
    # ========================================
    # BƯỚC 1: Nhập thông tin
    # ========================================
    print("\n📝 BƯỚC 1: Nhập thông tin")
    print("-" * 60)
    
    # Đường dẫn file audio
    audio_file = input("Đường dẫn file audio: ").strip()
    
    if not audio_file:
        print("❌ Bạn chưa nhập đường dẫn!")
        return
    
    if not os.path.exists(audio_file):
        print(f"❌ File không tồn tại: {audio_file}")
        return
    
    # Thông tin khác
    title = input("Tiêu đề (Enter = tên file): ").strip()
    if not title:
        title = os.path.basename(audio_file)
    
    description = input("Mô tả (Enter = bỏ qua): ").strip()
    
    language = input("Ngôn ngữ [ja/en/vi] (Enter = ja): ").strip() or "ja"
    
    # ========================================
    # BƯỚC 2: Upload audio lên S3
    # ========================================
    print("\n📤 BƯỚC 2: Upload audio lên S3")
    print("-" * 60)
    print(f"⏳ Đang upload {audio_file}...")
    
    result = manager.create_presentation(
        audio_file_path=audio_file,
        slide_file_path=None,  # Không có PDF
        title=title,
        description=description or f"Audio: {os.path.basename(audio_file)}",
        language=language,
        auto_transcribe=False  # Chưa transcribe ngay
    )
    
    if not result["success"]:
        print(f"❌ Lỗi upload: {result['error']}")
        return
    
    presentation_id = result["presentation_id"]
    
    print(f"✅ Upload thành công!")
    print(f"🆔 Presentation ID: {presentation_id}")
    print(f"🎵 S3 Key: {result['audio_s3_key']}")
    
    # ========================================
    # BƯỚC 3: Transcribe audio
    # ========================================
    print("\n🎤 BƯỚC 3: Transcribe audio")
    print("-" * 60)
    
    confirm = input("Bắt đầu transcribe? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("⏭️  Bỏ qua transcribe")
        print(f"\n💡 Để transcribe sau, chạy:")
        print(f"   manager.transcribe_presentation('{presentation_id}')")
        return
    
    print("⏳ Đang transcribe... (có thể mất vài phút)")
    
    transcript_result = manager.transcribe_presentation(presentation_id)
    
    if not transcript_result["success"]:
        print(f"❌ Lỗi transcribe: {transcript_result['error']}")
        return
    
    # ========================================
    # BƯỚC 4: Hiển thị kết quả
    # ========================================
    print("\n📝 BƯỚC 4: Kết quả")
    print("=" * 60)
    
    print(f"\n✅ Transcribe thành công!")
    print(f"\n📊 Thông tin:")
    print(f"  - Confidence: {transcript_result['confidence']:.2%}")
    print(f"  - Word count: {transcript_result['word_count']}")
    
    print(f"\n📝 TRANSCRIPT:")
    print("-" * 60)
    print(transcript_result["text"])
    print("-" * 60)
    
    # ========================================
    # BƯỚC 5: Lưu kết quả (optional)
    # ========================================
    print("\n💾 BƯỚC 5: Lưu kết quả")
    print("-" * 60)
    
    save = input("Lưu transcript vào file? (y/n): ").strip().lower()
    
    if save == 'y':
        output_file = f"transcript_{presentation_id}.txt"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Presentation ID: {presentation_id}\n")
            f.write(f"Title: {title}\n")
            f.write(f"Language: {language}\n")
            f.write(f"Confidence: {transcript_result['confidence']:.2%}\n")
            f.write(f"Word count: {transcript_result['word_count']}\n")
            f.write(f"\n{'-'*60}\n")
            f.write(f"TRANSCRIPT:\n")
            f.write(f"{'-'*60}\n\n")
            f.write(transcript_result["text"])
        
        print(f"✅ Đã lưu vào: {output_file}")
    
    # ========================================
    # BƯỚC 6: Tùy chọn khác
    # ========================================
    print("\n🔧 BƯỚC 6: Tùy chọn")
    print("-" * 60)
    print(f"1. Xem thông tin đầy đủ")
    print(f"2. Generate presigned URL")
    print(f"3. Xóa presentation")
    print(f"4. Xem tất cả presentations")
    print(f"0. Thoát")
    
    choice = input("\nChọn (Enter = 0): ").strip() or "0"
    
    if choice == "1":
        # Xem thông tin đầy đủ
        details = manager.get_presentation(presentation_id)
        if details["success"]:
            print(f"\n📊 Thông tin đầy đủ:")
            print(f"{details}")
    
    elif choice == "2":
        # Generate presigned URL
        url_result = manager.get_audio_url(presentation_id, expiration=3600)
        if url_result["success"]:
            print(f"\n🔗 Presigned URL (valid 1h):")
            print(f"{url_result['presigned_url']}")
    
    elif choice == "3":
        # Xóa presentation
        confirm_delete = input(f"\n⚠️  Xác nhận xóa {presentation_id}? (yes/no): ").strip().lower()
        if confirm_delete == "yes":
            delete_result = manager.delete_presentation(presentation_id, delete_files=True)
            if delete_result["success"]:
                print(f"✅ Đã xóa presentation!")
            else:
                print(f"❌ Lỗi: {delete_result['error']}")
    
    elif choice == "4":
        # Xem tất cả presentations
        all_pres = manager.list_presentations()
        print(f"\n📋 Tất cả presentations:")
        for p in all_pres:
            print(f"  - {p['presentation_id']}: {p['title']} ({p['status']})")
    
    print("\n" + "=" * 60)
    print("✅ HOÀN TẤT!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Đã hủy!")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
