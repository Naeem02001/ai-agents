# Prompt Engineering Concepts — Homework 1

While working on this homework, I tried different ways of writing the prompts for the AI agents. These are the three techniques that I found most useful in my project.

## 1. Role-Based Prompting

The first technique I used was giving each expert a specific role.

For example, I have a Database Read Expert for reading information from the database, a Database Write Expert for modifying the database, a Content Expert for questions about the resume, and an Orchestrator that decides which expert should handle a request.

I found this useful because each expert has a clear responsibility. The AI does not have to decide how to handle every type of request by itself.

For example, when I ask about information stored in the database, the Read Expert focuses on generating a SELECT query instead of trying to answer from general knowledge.

Overall, this approach worked well for my project because it made the different parts of the system more organized.

## 2. Clear Output Instructions

The second technique I used was giving the AI very clear instructions about the format of its response.

For the Database Read Expert, I instructed it to return only a valid SQLite SELECT query.

For the Database Write Expert, I instructed it to return one valid SQLite INSERT statement and not include explanations or other types of code.

For example, when I asked:

"Add Raspberry Pi to Embedded Systems Projects with skill level 8."

The Database Write Expert generated an INSERT statement for the skills table.

This was useful because the application expects a specific type of output from the expert. If the model added extra explanation around the SQL, it could cause problems when the application tries to process the result.

I found that being specific about the expected output made the responses more consistent.

## 3. Few-Shot Prompting

The third technique I tried was giving the model examples of the type of response I expected.

For example, the Database Read Expert has an example showing how a question about an institution can be converted into a SELECT query.

The Database Write Expert also has an example showing how a skill can be added to an experience.

These examples helped the model understand the expected structure instead of relying only on written instructions.

I found this especially useful for database operations because the model could follow the same general pattern when generating SQL for a new request.

## What I Learned

The three techniques worked well together.

Role-based prompting helped separate the responsibilities of the experts. Clear output instructions helped control the format of the generated responses. Few-shot examples helped the model understand the expected format through examples.

The most important thing I learned from this homework is that the way the prompt is written can make a big difference in how reliable the AI agent is. Giving the model a clear role, clear instructions, and a useful example made it easier to connect the AI responses with the actual database operations in my application.