let displayMessage = (message,color)=>
{
	let h1Tag = document.querySelector('#heading');
	h1Tag.innerText = message;
	h1Tag.style.color = color;
}
let gmBtn=document.querySelector('#gm-btn');
gmBtn.addEventListener('click',function()
{
	displayMessage('Good Morning',blue);
});