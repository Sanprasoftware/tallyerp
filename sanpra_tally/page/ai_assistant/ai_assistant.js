frappe.pages["ai_assistant"].on_page_load = function (wrapper) {

    let page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "AI Assistant",
        single_column: true
    });

    $(wrapper).find(".layout-main-section").html(`

        <div class="erp-ai-assistant">

            <h2>🤖 ERP AI Assistant</h2>

            <p>
                Ask questions about your ERP data.
            </p>

            <div class="ai-chat-box" id="ai-chat-box">

                <div class="ai-message">
                    Hello! Ask me anything about your ERP.
                </div>

            </div>

            <div class="ai-input-area">

                <input
                    type="text"
                    class="form-control"
                    id="ai-question"
                    placeholder="Ask anything about your ERP..."
                />

                <button
                    class="btn btn-primary"
                    id="ai-send">
                    Send
                </button>

            </div>

        </div>
    `);


    $("#ai-send").on("click", function () {

        let question = $("#ai-question").val().trim();

        if (!question) {
            frappe.msgprint("Please enter a question.");
            return;
        }


        // Display user message

        $("#ai-chat-box").append(`
            <div class="user-message">
                <b>You:</b> ${question}
            </div>
        `);


        // Clear textbox

        $("#ai-question").val("");


        // Show loading

        $("#ai-chat-box").append(`
            <div class="ai-message ai-loading">
                🤖 Thinking...
            </div>
        `);


        // Call Frappe backend

        frappe.call({

            method: "sanpra_tally.sanpra_tally.ai.api.ask",

            args: {
                question: question
            },

            callback: function (response) {

                $(".ai-loading").remove();


                if (response.message && response.message.success) {

                    $("#ai-chat-box").append(`
                        <div class="ai-message">
                            <b>AI:</b>
                            ${response.message.answer}
                        </div>
                    `);

                } else {

                    $("#ai-chat-box").append(`
                        <div class="ai-message">
                            ❌ Something went wrong.
                        </div>
                    `);

                }

            }

        });

    });


    // Allow Enter key to send

    $("#ai-question").on("keypress", function (e) {

        if (e.which === 13) {
            $("#ai-send").click();
        }

    });

};