#!/usr/bin/env python3

import asyncio
from LLMFunc import LLMScraperHandler

async def generate_enhanced_question_md():
    """Generate question.md with enhanced audio transcription analysis"""
    
    handler = LLMScraperHandler()
    
    request = {
        "url": "https://tds-llm-analysis.s-anand.net/demo-audio?email=23f2003481%40ds.study.iitm.ac.in&id=20574",
        "force_dynamic": True  # Force dynamic to get audio elements
    }
    
    print("🔄 Generating enhanced question.md...")
    result = await handler.handle_request(request)
    
    if result['success']:
        # Generate markdown with enhanced analysis
        markdown_output = handler.format_as_markdown(result)
        
        # Save to question.md
        with open('question.md', 'w', encoding='utf-8') as f:
            f.write(markdown_output)
        
        print("✅ Enhanced question.md generated with improved audio analysis")
        print("📊 Audio transcription now includes task interpretation and step-by-step guidance")
        
        # Show preview of audio section
        lines = markdown_output.split('\n')
        audio_section_start = None
        for i, line in enumerate(lines):
            if '## 🎵 SECTION 5:' in line:
                audio_section_start = i
                break
        
        if audio_section_start:
            print(f"\n📄 Audio section preview:")
            print("="*60)
            for line in lines[audio_section_start:audio_section_start+30]:
                print(line)
            print("="*60)
    else:
        print(f"❌ Failed to generate question.md: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(generate_enhanced_question_md())