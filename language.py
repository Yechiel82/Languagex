# from config import API_KEY
# import google.generativeai as genai
# import os

# genai.configure(api_key=os.environ["API_KEY])

# model = genai.GenerativeModel('gemini-1.5-flash')
# response = model.generate_content("Write a story about an AI and magic")
# print(response.text)
# # <!DOCTYPE html>
# # <html lang="en">
# # <head>
# #     <meta charset="UTF-8">
# #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# #     <title>Document Generator</title>
# #     <style>
# #         /* Basic Page Layout */
# #         body, html {
# #             margin: 0;
# #             padding: 0;
# #             height: 100%;
# #             font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; /* Common web-safe font */
# #             line-height: 1.6; /* Improves readability */
# #         }

# #         .container {
# #             display: flex;
# #             min-height: 100vh; 
# #             background: #f4f4f4; 
# #         }

# #         /* Sidebar Styles */
# #         .sidebar {
# #             width: 300px; 
# #             padding: 20px;
# #             background: #fff;
# #             box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1); 
# #         }

# #         .sidebar h2 {
# #             font-size: 1.5rem;
# #             margin-bottom: 20px;
# #             color: #333;
# #         }

# #         /* Form Styles */
# #         .sidebar form {
# #             display: flex;
# #             flex-direction: column; 
# #         }

# #         .sidebar label {
# #             font-weight: 500; 
# #             margin-bottom: 5px;
# #         }

# #         .sidebar input[type="text"],
# #         .sidebar select {
# #             padding: 10px;
# #             border: 1px solid #ddd;
# #             border-radius: 4px;
# #             margin-bottom: 15px;
# #         }

# #         .sidebar input[type="submit"] {
# #             background-color: #007bff; /* Bootstrap blue */
# #             color: white;
# #             padding: 10px 15px;
# #             border: none;
# #             border-radius: 4px;
# #             cursor: pointer;
# #         }

# #         .sidebar input[type="submit"]:hover {
# #             background-color: #0069d9; /* Darker blue on hover */
# #         }

# #         /* Main Content Area */
# #         .main-content {
# #             flex: 1;
# #             padding: 30px;
# #         }

# #         .document-view {
# #             background: #fff;
# #             padding: 20px;
# #             border-radius: 8px;
# #             box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
# #         }

# #         .welcome-message {
# #             text-align: center;
# #             padding-top: 100px; 
# #         }

# #         .welcome-message h1 {
# #             font-size: 2.5rem;
# #             margin-bottom: 15px;
# #         }

# #         .welcome-message p {
# #             font-size: 1.2rem;
# #             color: #555;
# #         }
# #     </style>
# # </head>
# # <body>

# #   <div class="container">
# #     <div class="sidebar">
# #       <h2>Document Settings</h2>
# #       <form id="documentSettingsForm">
# #         <label for="topic">Topic:</label><br>
# #         <input type="text" id="topic" name="topic" value="한국 여자"><br><br>
# #         <label for="language">Language:</label><br>
# #         <input type="text" id="language" name="language" value="Korean"><br><br>
# #         <label for="target">Target:</label><br>
# #         <input type="text" id="target" name="target" value="는 것"><br><br>
# #         <label for="level">Level:</label><br>
# #         <select id="level" name="level">
# #           <option value="Beginner">Beginner</option>
# #           <option value="Intermediate">Intermediate</option>
# #           <option value="Advanced" selected>Advanced</option>
# #         </select><br><br>
# #         <input type="submit" value="Generate Document">
# #       </form>
# #     </div>

# #     <div class="main-content">
# #       <div class="document-view" id="documentContent">
# #         <div class="welcome-message">
# #           <h1>Welcome!</h1>
# #           <p>Update the settings and click "Generate Document" to start.</p>
# #         </div>
# #       </div>
# #     </div>
# #   </div>



    
    
# # </body>
# # </html>
