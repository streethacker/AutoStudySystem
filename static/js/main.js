$(document).ready(function(){
	/*返回顶部*/
	$('#rocket').hide();
	$(window).scroll(function () {
		if ($(window).scrollTop() > 300) {
			$('#rocket').fadeIn(400);//当滑动栏向下滑动时，按钮渐现的时间
		} else {
			$('#rocket').fadeOut(0);//当页面回到顶部第一屏时，按钮渐隐的时间
		}
	});
	$('#rocket').click(function () {
		$('html,body').animate({
			scrollTop : '0px'
		}, 300);//返回顶部所用的时间 返回顶部也可调用goto()函数
	});
	//================登录退出==================================
	$("#user-widget").hide();
	$("#user-info").hover(function(){
			$("#user-widget").show();
		},
          function () {
		$("#user-widget").hide();
	   }
		);
		//================注册表单==================================
    
     $(".login-group input").blur(function(){
     	var node=$(this).val();
     	var error=$(this).prev();
     	if(node=="") error.html("必填！");
     	else error.html("");
     });
	 $("#recheckPassword").blur(function(){
     	var pw=$("#password").val();
     	var recheckpw=$("#recheckPassword").val();
        var error=$("#recheckPassword").prev();
     	if (pw!=recheckpw) {error.html("两次密码输入的不一致！")};
     });
     //================展开收起==================================
     $(".article-fold-a").click(function(){
     	 if($(this).text()=="展开")
     {
     	$(".article-fold p").css("height","auto");
	    $(this).html("收起");
	 }
	 else{
		$(".article-fold p").css("height","4em");
		$(this).html("展开");
	  }
     });
});