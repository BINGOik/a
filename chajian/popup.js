// 加载插件页面时，自动保存已输入过的api_key
document.addEventListener("DOMContentLoaded", () => {
  const key = localStorage.getItem("my_openai_api_key");
  if (key) {
    document.getElementById('api_key_input').value = key;
  }
});

// 主题逻辑处理
document.getElementById('download-domain').addEventListener('click', async () => {
  // 获取用户输入的 OpenAI API Key
  const api_key = document.getElementById('api_key_input').value.trim();
  if (!api_key) {
    alert("请输入 OpenAI API Key！");
    return;
  }
  // 保存 key，下次自动输入
  localStorage.setItem("my_openai_api_key", api_key);

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  // 传入api_key
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (api_key) => {
      (async function(api_key) {
        if (!api_key) {
          alert("未检测到 API Key，无法继续。");
          return;
        }
        
        // 传入readme文档
        let text = null;
        const [, owner, repo] = window.location.pathname.split('/');
        if (!owner || !repo) {
          alert('无法解析仓库地址，请确认这是 GitHub 仓库页面。');
          return;
        }
        const branches = ['main', 'master'];
        for (const b of branches) {
          try {
            const url = `https://raw.githubusercontent.com/${owner}/${repo}/${b}/README.md`;
            const res = await fetch(url);
            if (res.ok) {
              text = await res.text();
              break;
            }
          } catch (e) {}
        }
        if (!text) {
          alert('未能从 raw.githubusercontent.com 获取到 README.md');
          return;
        }

        // 利用flask后端完成逻辑
        try {
          const resp = await fetch('http://127.0.0.1:8000/domain', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, api_key })
          });
          if (!resp.ok) throw new Error(resp.statusText);

          const { result } = await resp.json();

          // 保存结果为txt文件
          if (result) {
            const resultBlob = new Blob([result], { type: "text/plain" });
            const resultFilename = `${owner}-${repo}-domain.txt`;
            const link = document.createElement('a');
            link.href = URL.createObjectURL(resultBlob);
            link.download = resultFilename;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(link.href);
          } else {
            alert("没有返回分类结果");
          }
        } catch (e) {
          console.error("分类提取失败：", e);
          alert("分类提取失败，请检查后端服务或网络：" + e.message);
        }
      })(api_key);
    },
    args: [api_key]
  });
});
