IMAGE_INTEGRATOR = """You are given two inputs: 

1. A formatted answer about a maintenance procedure
2. Original text chunks containing image references in the format `![](_page_X_Picture_Y.jpeg)`

Your task is to insert the exact image references from the original text chunks directly into the answer at the precise points where those steps appear, creating an interleaved document with images and text.

## Instructions

1. **Compare the answer with the text chunks**:
   - Identify all image references in the text chunks using the format `![](_page_X_Picture_Y.jpeg)`
   - Match the surrounding text in the chunks with corresponding steps in the answer

2. **For each matched step**:
   - Insert the exact image reference directly before the matching step
   - Preserve the exact image path as written in the text chunks
   - Do not add any captions, figure numbers, or descriptions
   - Keep the image references in their exact format: `![](_page_X_Picture_Y.jpeg)`

3. **Maintain exact sequence and numbering**:
   - Do not change the numbered sequence of steps in the answer
   - Do not add any text that wasn't in the original answer
   - Do not modify any technical content

4. **Only include images that directly relate**:
   - Insert only images that correspond to steps in the answer
   - Place each image immediately before the step it illustrates
   - Do not add extra formatting around the images

5. **Preserve image-specific references**:
   - Check if the original text chunks contain bold references to numbered items in the images (e.g., **1**, **2**, **3**)
   - If the corresponding step in the answer is missing these references, update the answer to include them
   - Example: If the chunk says "Remove the transmission dipstick (**1**)" but the answer only says "Remove the transmission dipstick", update it to "Remove the transmission dipstick (**1**)"
   - Only do this for numbered references that specifically relate to components shown in the images

## Example

### Original answer text:
```
15. Remove the transmission dipstick and check the oil level. The cold oil level after 2-3 minutes of idle must be above the HOT MIN line on the dipstick.
16. If the oil is low, add oil as required.
```

### Text chunk with image reference:
```
![](_page_179_Figure_21.jpeg)

3. Remove the transmission dipstick (**1**) and check the oil level. The cold oil level after 2-3 minutes of idle must be above the HOT MIN line on the dipstick.
```

### Expected enhanced output:
```
![](_page_179_Figure_21.jpeg)
15. Remove the transmission dipstick (**1**) and check the oil level. The cold oil level after 2-3 minutes of idle must be above the HOT MIN line on the dipstick.
16. If the oil is low, add oil as required.
```

---

## Input Data

<answer>
[ANSWER HERE]
</answer>

<raw_data>
[RAW DATA HERE]
</raw_data>

## Expected Output
Provide the enhanced answer with images interleaved exactly at their appropriate locations, using the exact image references from the text chunks. Also ensure that any bold-formatted image component references (like **1**, **2**) from the original text chunks are included in the corresponding steps of the answer."""