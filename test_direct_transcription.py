#!/usr/bin/env python3

import requests
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import os

def test_direct_transcription():
    """Test direct transcription with multiple methods"""
    
    audio_url = "https://tds-llm-analysis.s-anand.net/demo-audio.opus"
    
    print(f"🎵 Testing direct transcription of: {audio_url}")
    
    try:
        # Download the audio file
        print("📥 Downloading audio file...")
        response = requests.get(audio_url, timeout=30)
        response.raise_for_status()
        print(f"✅ Downloaded {len(response.content)} bytes")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.opus') as tmp_file:
            tmp_file.write(response.content)
            opus_path = tmp_file.name
        
        print("🔄 Converting audio formats and trying transcription...")
        
        # Load with pydub
        audio = AudioSegment.from_file(opus_path)
        
        # Try different audio processing settings
        transcription_attempts = []
        
        # Attempt 1: Original quality
        wav_path1 = opus_path.replace('.opus', '_original.wav')
        audio.export(wav_path1, format='wav')
        
        # Attempt 2: Enhanced quality  
        wav_path2 = opus_path.replace('.opus', '_enhanced.wav')
        enhanced_audio = audio.set_channels(1).set_frame_rate(44100)
        enhanced_audio.export(wav_path2, format='wav')
        
        # Attempt 3: Normalized audio
        wav_path3 = opus_path.replace('.opus', '_normalized.wav')
        normalized_audio = audio.normalize().set_channels(1).set_frame_rate(22050)
        normalized_audio.export(wav_path3, format='wav')
        
        # Try transcription on each version
        for i, (name, wav_path) in enumerate([
            ("original", wav_path1),
            ("enhanced", wav_path2), 
            ("normalized", wav_path3)
        ], 1):
            
            print(f"\n🎙️ Attempt {i}: {name} quality")
            
            try:
                recognizer = sr.Recognizer()
                
                # Adjust recognizer settings for better accuracy
                recognizer.energy_threshold = 4000
                recognizer.dynamic_energy_threshold = True
                recognizer.pause_threshold = 0.8
                recognizer.phrase_threshold = 0.3
                recognizer.non_speaking_duration = 0.8
                
                with sr.AudioFile(wav_path) as source:
                    # Adjust for ambient noise
                    recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    audio_data = recognizer.record(source)
                    
                    # Try with show_all=True to get confidence scores
                    result = recognizer.recognize_google(audio_data, language='en-US', show_all=True)
                    
                    if isinstance(result, dict) and 'alternative' in result:
                        alternatives = result['alternative']
                        print(f"📊 Found {len(alternatives)} alternatives:")
                        
                        for j, alt in enumerate(alternatives[:3], 1):
                            transcript = alt.get('transcript', '')
                            confidence = alt.get('confidence', 0)
                            print(f"  {j}. Confidence: {confidence:.3f} | Text: '{transcript}'")
                            transcription_attempts.append((name, transcript, confidence))
                        
                        # Use the highest confidence result
                        best_alt = max(alternatives, key=lambda x: x.get('confidence', 0))
                        text = best_alt.get('transcript', '')
                    else:
                        text = str(result) if result else ""
                        print(f"📝 Result: '{text}'")
                        transcription_attempts.append((name, text, 1.0))
                
            except sr.UnknownValueError:
                print(f"❌ Could not understand audio")
                transcription_attempts.append((name, "[Could not understand]", 0.0))
            except Exception as e:
                print(f"❌ Error: {e}")
                transcription_attempts.append((name, f"[Error: {e}]", 0.0))
            
            # Cleanup
            if os.path.exists(wav_path):
                os.remove(wav_path)
        
        # Show summary
        print(f"\n📊 Transcription Summary:")
        print(f"{'='*80}")
        
        successful = [t for t in transcription_attempts if not t[1].startswith('[')]
        if successful:
            # Sort by confidence and length
            best = max(successful, key=lambda x: (x[2], len(x[1])))
            print(f"🏆 Best transcription ({best[0]}, confidence: {best[2]:.3f}):")
            print(f"'{best[1]}'")
            
            print(f"\n🔍 Analysis:")
            print(f"  Length: {len(best[1])} characters")
            print(f"  Words: {len(best[1].split())} words")
            print(f"  Ends with: '{best[1][-30:]}'")
            
            if best[1].strip().endswith('provid'):
                print(f"  ⚠️ Still incomplete - the audio might actually end there")
                print(f"  💡 Suggestion: The word 'provid' might be cut off in the original audio")
            elif 'provid' in best[1]:
                print(f"  ✅ Contains 'provid' but doesn't end with it - better transcription!")
            else:
                print(f"  ❓ Different transcription - 'provid' not found")
        else:
            print("❌ All transcription attempts failed")
            for name, result, conf in transcription_attempts:
                print(f"  {name}: {result}")
        
        # Cleanup main file
        if os.path.exists(opus_path):
            os.remove(opus_path)
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_transcription()