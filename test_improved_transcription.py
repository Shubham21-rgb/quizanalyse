#!/usr/bin/env python3

import asyncio
import sys
import os

# Add current directory to path to import LLMFunc
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from LLMFunc import LLMScraperHandler

async def test_audio_transcription():
    """Test the improved audio transcription on the demo-audio page"""
    
    handler = LLMScraperHandler()
    
    # Test with the audio task URL
    audio_url = "https://tds-llm-analysis.s-anand.net/demo-audio"
    
    print("🎵 Testing improved audio transcription...")
    print(f"📍 URL: {audio_url}")
    
    request = {
        "url": audio_url,
        "force_dynamic": True  # Force dynamic mode to render JavaScript
    }
    
    try:
        print("🔄 Scraping page and transcribing audio...")
        result = await handler.handle_request(request)
        
        if result['success']:
            data = result['data']
            
            print(f"📊 Scraping result:")
            print(f"  Method: {result.get('method')}")
            print(f"  Audio elements: {len(data.get('audio_elements', []))}")
            print(f"  Audio transcriptions: {len(data.get('audio_transcriptions', []))}")
            
            # Debug: Show what audio elements were found
            if data.get('audio_elements'):
                print(f"\n🎵 Audio elements detected:")
                for i, audio in enumerate(data['audio_elements'], 1):
                    print(f"  {i}. {audio['src']} (controls: {audio.get('controls', False)})")
            else:
                print("❌ No audio elements detected in HTML")
            
            # Check if audio transcriptions were found
            if data.get('audio_transcriptions'):
                print(f"✅ Found {len(data['audio_transcriptions'])} audio file(s)")
                
                for i, transcription in enumerate(data['audio_transcriptions'], 1):
                    print(f"\n🎧 Audio {i}: {transcription['url']}")
                    print(f"📊 Status: {transcription['status']}")
                    print(f"📝 Transcription:")
                    print(f"{'='*60}")
                    print(transcription['transcription'])
                    print(f"{'='*60}")
                    
                    # Analyze the transcription
                    text = transcription['transcription']
                    if text and not text.startswith('[Error'):
                        print(f"\n🔍 Analysis:")
                        print(f"  Length: {len(text)} characters")
                        print(f"  Words: {len(text.split())} words")
                        print(f"  Ends with: '{text[-20:]}'")
                        
                        # Check if it's still incomplete
                        if text.endswith('provid'):
                            print(f"  ⚠️ Still incomplete - ends with 'provid'")
                        else:
                            print(f"  ✅ Appears complete")
            else:
                print("❌ No audio transcriptions found")
                
                # If no transcriptions but audio elements exist, try manual transcription
                if data.get('audio_elements'):
                    print("\n🔧 Attempting manual transcription...")
                    audio_url = data['audio_elements'][0]['src']
                    print(f"📥 Downloading: {audio_url}")
                    
                    # Manual test of transcription
                    import requests
                    from LLMFunc import WebScraper
                    
                    scraper = WebScraper()
                    try:
                        audio_response = requests.get(audio_url, timeout=30)
                        audio_response.raise_for_status()
                        
                        print(f"✅ Downloaded {len(audio_response.content)} bytes")
                        print("🎙️ Transcribing...")
                        
                        transcription = scraper._transcribe_audio(audio_response.content, audio_url)
                        print(f"📝 Manual transcription result:")
                        print(f"{'='*60}")
                        print(transcription)
                        print(f"{'='*60}")
                        
                    except Exception as e:
                        print(f"❌ Manual transcription failed: {e}")
                
            # Also check text content for any audio-related information
            text_content = data.get('text_content', '')
            if 'audio' in text_content.lower() or 'cutoff' in text_content.lower():
                print(f"\n📄 Text content contains audio/cutoff references:")
                lines = text_content.split('\n')
                relevant_lines = [line.strip() for line in lines if 'audio' in line.lower() or 'cutoff' in line.lower()]
                for line in relevant_lines[:10]:
                    print(f"  - {line}")
                    
        else:
            print(f"❌ Scraping failed: {result.get('error')}")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_audio_transcription())