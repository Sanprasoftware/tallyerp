frappe.provide("sanpra_tally.ai_assistant");


// ============================================================
// ERP AI ASSISTANT - DESK HOME
// ============================================================

sanpra_tally.ai_assistant.add_desk_box = function () {

    // --------------------------------------------------------
    // Don't create twice
    // --------------------------------------------------------
    if ($("#sanpra_tally-ai-assistant-box").length) {
        return;
    }


    // --------------------------------------------------------
    // Only run on Desk home
    // --------------------------------------------------------
    const route = frappe.get_route();

    if (route[0] !== "" && route[0] !== "desk") {
        return;
    }


    // --------------------------------------------------------
    // Get Desk container
    // --------------------------------------------------------
    const container = $(".layout-main-section").first();

    if (!container.length) {
        console.log("Sanpra Tally AI: Desk container not found");
        return;
    }


    // --------------------------------------------------------
    // Create Assistant UI
    // --------------------------------------------------------
    const box = $(`
        <div id="sanpra_tally-ai-assistant-box"
             style="
                margin: 20px;
                padding: 24px;
                border: 1px solid #d1d8dd;
                border-radius: 12px;
                background: #ffffff;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
             ">

            <!-- Header -->
            <div style="
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 5px;
             ">
                🤖 ERP AI Assistant
            </div>

            <div style="
                color: #6c7680;
                margin-bottom: 18px;
             ">
                Ask questions about your ERP data
            </div>


            <!-- Input -->
            <div style="
                display: flex;
                gap: 10px;
                align-items: center;
             ">

                <input
                    type="text"
                    id="sanpra_tally-ai-question"
                    class="form-control"
                    placeholder="Ask anything about your ERP..."
                    autocomplete="off"
                    style="
                        flex: 1;
                        height: 42px;
                    "
                />

                <button
                    type="button"
                    class="btn btn-primary"
                    id="sanpra_tally-ai-send"
                    style="
                        height: 42px;
                        min-width: 75px;
                    ">
                    Ask
                </button>

            </div>


            <!-- Conversation -->
            <div
                id="sanpra_tally-ai-answer"
                style="
                    margin-top: 20px;
                ">
            </div>

        </div>
    `);


    // --------------------------------------------------------
    // Insert Assistant
    // --------------------------------------------------------
    container.prepend(box);

    console.log(
        "Sanpra Tally AI: Desk AI box added"
    );


    // ========================================================
    // ASK BUTTON
    // ========================================================

    $("#sanpra_tally-ai-send").on("click", function () {

        const question = $("#sanpra_tally-ai-question")
            .val()
            .trim();


        // ----------------------------------------------------
        // Empty question
        // ----------------------------------------------------

        if (!question) {

            frappe.msgprint(
                "Please enter a question."
            );

            return;
        }


        // ----------------------------------------------------
        // Button
        // ----------------------------------------------------

        const send_button =
            $("#sanpra_tally-ai-send");

        send_button
            .prop("disabled", true)
            .text("Thinking...");


        // ----------------------------------------------------
        // Create conversation
        // ----------------------------------------------------

        const conversation = $(`
            <div
                class="sanpra_tally-ai-conversation"
                style="
                    margin-top: 15px;
                ">

                <!-- User question -->
                <div style="
                    padding: 12px 16px;
                    margin-bottom: 10px;
                    background: #eef4ff;
                    border-radius: 10px;
                    border: 1px solid #dbe7ff;
                ">

                    <div style="
                        font-weight: 600;
                        margin-bottom: 4px;
                    ">
                        You
                    </div>

                    <div style="
                        line-height: 1.5;
                        word-break: break-word;
                    ">
                        ${frappe.utils.escape_html(question)}
                    </div>

                </div>


                <!-- AI answer -->
                <div style="
                    padding: 12px 16px;
                    background: #f5f7fa;
                    border-radius: 10px;
                    border: 1px solid #e5e7eb;
                ">

                    <div style="
                        font-weight: 600;
                        margin-bottom: 4px;
                    ">
                        🤖 AI
                    </div>

                    <div
                        class="sanpra_tally-ai-response-text"
                        style="
                            line-height: 1.6;
                            word-break: break-word;
                        ">
                        🤖 Thinking...
                    </div>

                </div>

            </div>
        `);


        // Add below previous conversation
        $("#sanpra_tally-ai-answer").append(
            conversation
        );


        // Clear input
        $("#sanpra_tally-ai-question").val("");


        // Scroll to latest question
        conversation[0].scrollIntoView({
            behavior: "smooth",
            block: "nearest"
        });


        // ====================================================
        // CALL PYTHON BACKEND
        // ====================================================

        frappe.call({

            method:
                "sanpra_tally.sanpra_tally.ai.api.ask",

            args: {
                question: question
            },


            // ------------------------------------------------
            // Success
            // ------------------------------------------------

            callback: function (response) {

                console.log(
                    "Sanpra Tally AI response:",
                    response
                );


                const response_box =
                    conversation.find(
                        ".sanpra_tally-ai-response-text"
                    );


                // ------------------------------------------------
                // Successful response
                // ------------------------------------------------

                if (
                    response.message &&
                    response.message.success
                ) {

                    const answer =
                        response.message.answer || "";


                    response_box.html(
                        frappe.utils.escape_html(
                            answer
                        ).replace(
                            /\n/g,
                            "<br>"
                        )
                    );


                } else {

                    // ------------------------------------------------
                    // Unsuccessful response
                    // ------------------------------------------------

                    let error_message =
                        "Unable to get an answer.";


                    if (
                        response.message &&
                        response.message.error
                    ) {

                        error_message =
                            response.message.error;
                    }


                    response_box.html(`
                        <span style="
                            color: #b42318;
                        ">
                            ❌ ${frappe.utils.escape_html(
                                error_message
                            )}
                        </span>
                    `);
                }
            },


            // ------------------------------------------------
            // Server error
            // ------------------------------------------------

            error: function (error) {

                console.error(
                    "Sanpra Tally AI server error:",
                    error
                );


                const response_box =
                    conversation.find(
                        ".sanpra_tally-ai-response-text"
                    );


                response_box.html(`
                    <span style="
                        color: #b42318;
                    ">
                        ❌ Server error.
                        Please check the ERPNext server logs.
                    </span>
                `);
            },


            // ------------------------------------------------
            // Always
            // ------------------------------------------------

            always: function () {

                send_button
                    .prop("disabled", false)
                    .text("Ask");

                $("#sanpra_tally-ai-question").focus();
            }

        });

    });


    // ========================================================
    // ENTER KEY
    // ========================================================

    $("#sanpra_tally-ai-question").on(
        "keypress",
        function (e) {

            if (e.which === 13) {

                e.preventDefault();

                $("#sanpra_tally-ai-send").click();
            }
        }
    );

};


// ============================================================
// WAIT FOR DESK
// ============================================================

sanpra_tally.ai_assistant.wait_for_desk = function () {

    // Already exists
    if ($("#sanpra_tally-ai-assistant-box").length) {
        return;
    }


    // Current route
    const route = frappe.get_route();


    // Only Desk home
    if (route[0] !== "" && route[0] !== "desk") {
        return;
    }


    // Wait until Desk container exists
    if (!$(".layout-main-section").length) {

        setTimeout(
            sanpra_tally.ai_assistant.wait_for_desk,
            500
        );

        return;
    }


    // Add Assistant
    sanpra_tally.ai_assistant.add_desk_box();
};


// ============================================================
// DESK PAGE CHANGE
// ============================================================

$(document).on("page-change", function () {

    setTimeout(
        sanpra_tally.ai_assistant.wait_for_desk,
        1000
    );

});


// ============================================================
// INITIAL LOAD
// ============================================================

setTimeout(
    sanpra_tally.ai_assistant.wait_for_desk,
    1500
);
