import asyncio

import edge_tts

VOICE = "id-ID-GadisNeural"
TEXT = "Halo tes satu dua tiga."


async def check_voice():
    print(f"Checking voice: {VOICE}")

    # 1. Check Metadata
    voices = await edge_tts.list_voices()
    target_voice = next((v for v in voices if v["ShortName"] == VOICE), None)

    if target_voice:
        print("Voice found!")
        print(f"  Name: {target_voice['ShortName']}")
        print(f"  Gender: {target_voice['Gender']}")
        print(f"  Locale: {target_voice['Locale']}")
        print(f"  Status: {target_voice.get('Status')}")
        # print(f"  Metadata: {target_voice}") # Full dump
    else:
        print("Voice NOT found in list!")
        return

    # 2. Test Synthesis
    print("\nRunning synthesis check...")
    communicate = edge_tts.Communicate(TEXT, VOICE)

    boundary_count = 0
    audio_chunks = 0
    other_events = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks += 1
        elif chunk["type"] == "WordBoundary":
            boundary_count += 1
            print(f"  [Boundary] {chunk}")
        else:
            other_events.append(chunk)
            print(f"  [Other] {chunk}")

    print("\nResults:")
    print(f"  Audio chunks: {audio_chunks}")
    print(f"  Word Boundaries: {boundary_count}")
    print(f"  Other events: {len(other_events)}")

    if boundary_count > 0:
        print("\n[SUCCESS] Voice SUPPORTS highlights!")
    else:
        print("\n[FAIL] Voice DOES NOT return boundaries in this test.")


if __name__ == "__main__":
    asyncio.run(check_voice())
