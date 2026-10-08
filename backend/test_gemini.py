from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

response = client.models.generate_content(
model="gemini-3.8-flash",
contents="Reply with exactly: Gemini connection successfull."
)

print(response.text)
