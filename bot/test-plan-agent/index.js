/**
 * This is the main entrypoint to your Probot app
 * @param {import('probot').Probot} app
 */
export default (app) => {
  // Your code here
  app.log.info("Yay, the app was loaded!");

  // Listen for new issues
  app.on("issues.opened", async (context) => {
    const issueComment = context.issue({
      body: "Thanks for opening this issue!",
    });
    return context.octokit.issues.createComment(issueComment);
  });

  // 1. Listen for new PRs and comment
  app.on("pull_request.opened", async (context) => {
    app.log.info("pull_request opened event received");
    const prComment = context.issue({
      body: "Thanks for submitting this pull request! We appreciate your contribution.",
    });
    return context.octokit.issues.createComment(prComment);
  });

 // 单独监听 PR 评论
  app.on("issue_comment.created", async (context) => {
    app.log.info("Comment created event received");
    
    // 确认这是 PR 上的评论而不是 issue 上的评论
    const issueData = await context.octokit.issues.get(context.issue());
    if (!issueData.data.pull_request) {
      app.log.info("This comment is on an issue, not a PR");
      return;
    }
    
    app.log.info("This comment is on a PR");
    
    // 检查是否包含 /generate 命令
    const commentBody = context.payload.comment.body || "";
    if (commentBody.includes("/generate")) {
      app.log.info("Generate command detected in comment");
      const prUrl = context.payload.issue.html_url;
      
      const response = context.issue({
        body: `Generating test plan for PR: ${prUrl}`,
      });
      
      return context.octokit.issues.createComment(response);
    }
  });

    // 监听 PR 正文中的 /generate 命令
    app.on(["pull_request.opened", "pull_request.edited"], async (context) => {
      app.log.info(`PR ${context.payload.action} event received`);
      
      const prBody = context.payload.pull_request.body || "";
      if (prBody.includes("/generate")) {
        app.log.info("Generate command detected in PR body");
        const prUrl = context.payload.pull_request.html_url;
        
        const response = context.issue({
          body: `Generating test plan for PR: ${prUrl}`,
        });
        
        return context.octokit.issues.createComment(response);
      }
    });
    
};