let registerForm=document.querySelector('#register-form');
registerForm.addEventListener('submit',function(event)
{
	event.preventDefault();
	validate();
});
//validate function
let validate=()=>
{
	checkUserName();
}
//checkUserName.
let checkUserName=()=>
{
	let inputElement=document.querySelector('#username');
	let inputFeedback=document.querySelector('#username-feedback');
	let regEx=/^[a-zA-Z0-9]{4,10}$/;
	if(regEx.test(inputElement.value))
	{
		alert('enter proper Name');
		makeValid(inputElement,inputFeedback);
	}
	else
	{
		alert('enter Wrong Name');
		makeInValid(inputElement,inputFeedback);
	}
}
let makeValid-(inputElement,inputFeedback)=>
{
	inputElement.classList.add('is-form-valid');
	inputElement.classList.remove('is-form-invalid');
	inputFeedback.classList.add('text-success');
	inputFeedback.classList.remove('text-danger');
	inputFeedback.innerText='Looks Great';
}
let makeInValid-(inputElement,inputFeedback)=>
{
	inputElement.classList.remove('is-form-valid');
	inputElement.classList.add('is-form-invalid');
	inputFeedback.classList.remove('text-success');
	inputFeedback.classList.add('text-danger');
	inputFeedback.innerText=`please enter ${placeholder}`;
}
